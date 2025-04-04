import asyncio
import platform
import time
from typing import TYPE_CHECKING, Callable

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401

from hummingbot.strategy.cross_exchange_arb_logger.start import start


class CheckArbCommand:
    def check_arb(
        self,  # type: HummingbotApplication
        exchange_1_market_1: str,
        exchange_2_market_2: str,
    ):
        safe_ensure_future(
            self.check_arb_async(exchange_1_market_1, exchange_2_market_2),
            loop=self.ev_loop,
        )

    async def _run_clock(self):
        with self.clock as clock:
            await clock.run()

    async def wait_till_ready(
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

    async def check_arb_async(
        self,  # type: HummingbotApplication
        exchange_1_market_1: str,
        exchange_2_market_2: str,
    ):
        exchange_1, market_1 = exchange_1_market_1.split(":")
        exchange_2, market_2 = exchange_2_market_2.split(":")

        self.notify(
            f"Starting check_arb command with {exchange_1}, {exchange_2}, {market_1}, {market_2}"
        )
        self.strategy_file_name = "conf_cross_exchange_arb_logger_1.yml"
        self.strategy_name = "cross_exchange_arb_logger"
        self._last_started_strategy_file = self.strategy_file_name

        # If macOS, disable App Nap.
        if platform.system() == "Darwin":
            import appnope

            appnope.nope()

        self._initialize_notifiers()

        start(self, exchange_1, market_1, exchange_2, market_2)

        self.notify(
            f"\nStatus check complete. Starting '{self.strategy_name}' strategy..."
        )
        await self.start_market_making()

        # We always start the RateOracle. It is required for PNL calculation.
        RateOracle.get_instance().start()

    async def start_market_making(
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
                await self.wait_till_ready(self.kill_switch.start)
        except Exception as e:
            self.logger().error(str(e), exc_info=True)
