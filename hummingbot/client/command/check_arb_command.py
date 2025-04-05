import asyncio
import platform
import time
from typing import TYPE_CHECKING, Callable

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401

from hummingbot.strategy.cross_exchange_arb_logger.start import ExchangeInstrumentPair, start


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

    # TODO Change it to take just one market. I am not going to check for equivalent markets
    async def _check_arb_async(
        self,  # type: HummingbotApplication
        exchange_instrument_pairs: list[str],
        with_fees: bool,
    ):

        exchange_instrument_pairs_sanitized = [
            ExchangeInstrumentPair(
                *exchange_instrument.split(":")
            ) for exchange_instrument in exchange_instrument_pairs
        ]
        self.notify(
            f"Starting check_arb command with {exchange_instrument_pairs_sanitized}, {with_fees}"
        )

        # Strategy dependency
        self.strategy_file_name = "conf_cross_exchange_arb_logger_1.yml"
        self.strategy_name = "cross_exchange_arb_logger"
        self._last_started_strategy_file = self.strategy_file_name

        # If macOS, disable App Nap.
        if platform.system() == "Darwin":
            import appnope

            appnope.nope()

        self._initialize_notifiers()

        start(self, exchange_instrument_pairs_sanitized, with_fees)

        self.notify(
            f"\nStatus check complete. Starting '{self.strategy_name}' strategy..."
        )
        await self._start_market_making()

        # We always start the RateOracle. It is required for PNL calculation.
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
            self.logger().info("start command initiated.")

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
