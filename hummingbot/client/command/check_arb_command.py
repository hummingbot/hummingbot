import asyncio
import platform
import re
import time
from typing import TYPE_CHECKING, Callable, Literal

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401

from hummingbot.client.settings import AllConnectorSettings, required_exchanges, requried_connector_trading_pairs
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
from hummingbot.strategy.cross_exchange_arb_logger.data_types import ExchangeInstrumentPair
from hummingbot.strategy.cross_exchange_arb_logger.start import start

INSTRUMENT_PATTERN = re.compile(r"^[A-Z0-9]+-[A-Z0-9]+$")


class InvalidUserInputError(ValueError):
    def __init__(self, message: str, value: str = "", suggestion: str = ""):
        full_message = f"[Invalid Input] {message}"
        if value:
            full_message += f" → '{value}'"
        if suggestion:
            full_message += f"\nHint: {suggestion}"
        super().__init__(full_message)
        self.value = value
        self.suggestion = suggestion


class CheckArbCommand:
    def check_arb(
        self,  # type: HummingbotApplication
        exchange_instrument_pairs: list[str],
        with_fees: bool,
    ) -> None:
        safe_ensure_future(
            self._check_arb_async(exchange_instrument_pairs, with_fees),
            loop=self.ev_loop,
        )

    async def _check_arb_async(
        self,  # type: HummingbotApplication
        exchange_instrument_pairs: list[str],
        with_fees: bool,
    ):
        self.app.clear_input()
        self.placeholder_mode = True
        self.app.hide_input = True

        # This should ensure that the exchanges and instruments are suitable/valid for the strategy
        try:
            exchange_instrument_pairs_sanitized = await self._get_sanitized_exchange_instrument_pairs(exchange_instrument_pairs)
        except InvalidUserInputError as e:
            self.notify(str(e))
            return e
        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

        # Strategy dependency
        self.strategy_file_name = "conf_cross_exchange_arb_logger_1.yml"
        self.strategy_name = "cross_exchange_arb_logger"
        self._last_started_strategy_file = self.strategy_file_name

        # If macOS, disable App Nap.
        if platform.system() == "Darwin":
            import appnope
            appnope.nope()

        self._initialize_notifiers()

        self.notify(f"Starting '{self.strategy_name}' strategy...")
        self.placeholder_mode = False
        self.app.hide_input = False
        self.app.change_prompt(prompt=">>> ")

        # Strategy initializer
        await start(self, exchange_instrument_pairs_sanitized, with_fees)

        await self._start_market_making()

        # We always start the RateOracle. It is required for PNL calculation.
        # TODO is this needed?
        RateOracle.get_instance().start()

    # DO NOT TOUCH
    async def _start_market_making(
        self,  # type: HummingbotApplication
    ):
        try:
            self.start_time = time.time() * 1e3  # Time in milliseconds
            tick_size = self.client_config_map.tick_size
            self.logger().info(f"Creating the clock with tick size: {tick_size}")
            self.clock = Clock(ClockMode.REALTIME, tick_size=tick_size)
            for market in self.markets.values():
                if market is not None:
                    self.clock.add_iterator(market)
                    self.markets_recorder.restore_market_states(
                        self.strategy_file_name, market
                    )
                    if len(market.limit_orders) > 0:
                        self.notify(
                            f"Canceling dangling limit orders on {market.name}..."
                        )
                        await market.cancel_all(10.0)
            if self.strategy:
                self.clock.add_iterator(self.strategy)
            self.strategy_task: asyncio.Task = safe_ensure_future(
                self._run_clock(), loop=self.ev_loop
            )
            self.notify(
                f"\n'{self.strategy_name}' strategy started.\n"
                f"Run `status` command to query the progress."
            )
            self.logger().info("check_arb command initiated.")

            if self._trading_required:
                self.kill_switch = (
                    self.client_config_map.kill_switch_mode.get_kill_switch(self)
                )
                await self._wait_till_ready(self.kill_switch.start)
        except Exception as e:
            self.logger().error(str(e), exc_info=True)

    # DO NOT TOUCH
    async def _wait_till_ready(
        self,  # type: HummingbotApplication
        func: Callable,
        *args,
        **kwargs,
    ):
        while True:
            all_ready = all([market.ready for market in self.markets.values()])
            if not all_ready:
                await asyncio.sleep(0.5)
            else:
                return func(*args, **kwargs)

    # DO NOT TOUCH
    async def _run_clock(self):
        with self.clock as clock:
            await clock.run()

    async def _get_sanitized_exchange_instrument_pairs(self, exchange_instrument_pairs: list[str]) -> list[ExchangeInstrumentPair]:
        # This is what ends up getting passed to the strategy
        # it's a set because we want 'distinct' exchange instrument pairs
        sanitized_exchange_instrument_pairs: set[ExchangeInstrumentPair] = set()

        # all exchanges passed in by the user are checked against this set. Any user provided
        # exchanges that aren't in this set will either cause the app to raise, or re prompt
        known_exchanges = set(AllConnectorSettings.get_connector_settings().keys())

        # For the time being, we will only support arbitrage opportunities for the exact same market
        # We could allow equivalent symbols such as USDT and USDC, but that is beyond the scope of this
        # MVP. Potentially could be an attribute on self, but unsure.
        instruments: set[str] = set()

        # We require at least two exchanges for cross exchange arbitrage,
        # hence the range(2). If the user did not provide 2 input values,
        # IndexError is raised, and we prompt for input
        for i in range(2):
            try:
                exchange_instrument_pair = exchange_instrument_pairs[i]
            except IndexError:
                sanitized = await self._prompt_for_sanitized_exchange_instrument_pair(
                    instruments,
                    "first" if i == 0 else "second",
                    known_exchanges,
                )
            else:
                # Sanitizing a string provided on initial command. Will raise if invalid
                sanitized = sanitize_exchange_instrument_pair(exchange_instrument_pair, known_exchanges)
                # The below should probably not live here, given a similar check
                # exists in _prompt_for_sanitized_exchange_instrument_pair
                self._check_instrument(sanitized, instruments)
            # Add either an initially provided or prompted sanitized input
            sanitized_exchange_instrument_pairs.add(sanitized)

        if len(sanitized_exchange_instrument_pairs) == 1:
            self.notify("Duplicate exchange instrument pairs provided.")
            sanitized = await self._prompt_for_sanitized_exchange_instrument_pair(
                instruments,
                "second",
                known_exchanges,
            )
            sanitized_exchange_instrument_pairs.add(sanitized)

        # Sanitize any additional inputs
        for exchange_instrument_pair in exchange_instrument_pairs[2:]:
            sanitized = sanitize_exchange_instrument_pair(exchange_instrument_pair, known_exchanges)
            self._check_instrument(sanitized, instruments)
            sanitized_exchange_instrument_pairs.add(sanitized)

        for sanitized_exchange_instrument_pair in sanitized_exchange_instrument_pairs:
            # TODO why is this necessary?
            required_exchanges.add(sanitized_exchange_instrument_pair.exchange_name)
            requried_connector_trading_pairs.setdefault(sanitized_exchange_instrument_pair.exchange_name, []).append(
                sanitized_exchange_instrument_pair.instrument_name
            )

        return list(sanitized_exchange_instrument_pairs)

    async def _prompt_for_sanitized_exchange_instrument_pair(
        self,
        instruments: set[str],
        n: Literal["first", "second"],
        known_exchanges: set[str],
    ) -> ExchangeInstrumentPair:
        prompt = f"Please enter the {n} exchange instrument pair you would like to check >>> "
        # Keep prompting until user provides a valid input
        while True:
            exchange_instrument_pair = await self.app.prompt(prompt=prompt)
            try:
                sanitized = sanitize_exchange_instrument_pair(exchange_instrument_pair, known_exchanges)
            except InvalidUserInputError as e:
                self.notify(str(e))
                continue
            try:
                self._check_instrument(sanitized, instruments)
            except InvalidUserInputError:
                self.notify(f"Arbitrage between different instruments is not supported. {next(iter(instruments))} has already been specified")
                continue
            return sanitized

    def _check_instrument(self, pair: ExchangeInstrumentPair, instruments: set[str]) -> None:
        instruments.add(pair.instrument_name)
        if len(instruments) > 1:
            err = InvalidUserInputError(
                message="Arbitrage between different instruments is not supported.",
                value=instruments,
            )
            # We need to remove it because we can be in the situation where
            # we keep prompting the user for input until its valid
            instruments.remove(pair.instrument_name)
            self.notify(str(err))
            raise err


def sanitize_exchange_instrument_pair(exchange_instrument_pair: str, known_exchanges: set[str]) -> ExchangeInstrumentPair:
    # trim whitespace
    exchange_instrument_pair = "".join(exchange_instrument_pair.split())

    try:
        exchange, instrument = exchange_instrument_pair.split(":")
    except ValueError:
        raise InvalidUserInputError(
            message="Expected format 'exchange:market'",
            value=exchange_instrument_pair,
            suggestion="e.g. binance:BTC-USDT"
        )

    exchange = exchange.lower()
    instrument = instrument.upper()

    if exchange not in known_exchanges:
        raise InvalidUserInputError(
            message=f"Unknown exchange '{exchange}'",
            value=exchange,
            suggestion="Check that the connector is installed and spelled correctly."
        )

    if not INSTRUMENT_PATTERN.match(instrument):
        raise InvalidUserInputError(
            message=f"Invalid instrument format '{instrument}'",
            suggestion="Expected something like BTC-USDT"
        )

    return ExchangeInstrumentPair(exchange, instrument)


async def is_trading_pair_supported(exchange: str, trading_pair: str) -> bool:
    await TradingPairFetcher.get_instance().ready  # Ensure fetcher is ready
    trading_pairs = TradingPairFetcher.get_instance().trading_pairs(exchange)
    return trading_pair in trading_pairs
