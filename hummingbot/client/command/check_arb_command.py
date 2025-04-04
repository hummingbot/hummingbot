import asyncio
import platform
import time
from typing import TYPE_CHECKING, Callable, Optional

from hummingbot.client.settings import required_exchanges
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
        safe_ensure_future(self.import_config_file())

    async def import_config_file(
            self,  # type: HummingbotApplication
    ):
        file_name = "conf_cross_exchange_arb_logger_1.yml"
        self.app.clear_input()
        required_exchanges.clear()
        self.strategy_file_name = file_name
        self.strategy_name = "cross_exchange_arb_logger"
        self.strategy_config_map = {}
        self.app.change_prompt(prompt=">>> ")
        self.start()

    async def _run_clock(self):
        with self.clock as clock:
            await clock.run()

    async def wait_till_ready(self,  # type: HummingbotApplication
                              func: Callable, *args, **kwargs):
        while True:
            all_ready = all([market.ready for market in self.markets.values()])
            if not all_ready:
                await asyncio.sleep(0.5)
            else:
                return func(*args, **kwargs)

    def start(self,  # type: HummingbotApplication
              log_level: Optional[str] = None,
              script: Optional[str] = None,
              conf: Optional[str] = None,
              is_quickstart: Optional[bool] = False):
        safe_ensure_future(self.start_check(), loop=self.ev_loop)

    async def start_check(self,  # type: HummingbotApplication
                          log_level: Optional[str] = None,
                          script: Optional[str] = None,
                          conf: Optional[str] = None,
                          is_quickstart: Optional[bool] = False):
        self.notify("Starting START command")
        self._last_started_strategy_file = self.strategy_file_name

        # If macOS, disable App Nap.
        if platform.system() == "Darwin":
            import appnope
            appnope.nope()

        self._initialize_notifiers()

        self._initialize_strategy(self.strategy_name)

        self.notify(f"\nStatus check complete. Starting '{self.strategy_name}' strategy...")
        await self.start_market_making()

        # We always start the RateOracle. It is required for PNL calculation.
        RateOracle.get_instance().start()

    async def start_market_making(self,  # type: HummingbotApplication
                                  ):
        try:
            self.start_time = time.time() * 1e3  # Time in milliseconds
            tick_size = self.client_config_map.tick_size
            self.logger().info(f"Creating the clock with tick size: {tick_size}")
            self.clock = Clock(ClockMode.REALTIME, tick_size=tick_size)
            for market in self.markets.values():
                if market is not None:
                    self.clock.add_iterator(market)
                    self.markets_recorder.restore_market_states(self.strategy_file_name, market)
                    if len(market.limit_orders) > 0:
                        self.notify(f"Canceling dangling limit orders on {market.name}...")
                        await market.cancel_all(10.0)
            if self.strategy:
                self.clock.add_iterator(self.strategy)
            self.strategy_task: asyncio.Task = safe_ensure_future(self._run_clock(), loop=self.ev_loop)
            self.notify(f"\n'{self.strategy_name}' strategy started.\n"
                        f"Run `status` command to query the progress.")
            self.logger().info("start command initiated.")

            if self._trading_required:
                self.kill_switch = self.client_config_map.kill_switch_mode.get_kill_switch(self)
                await self.wait_till_ready(self.kill_switch.start)
        except Exception as e:
            self.logger().error(str(e), exc_info=True)

    def _initialize_strategy(self, strategy_name: str):
        start(self, "binance", "ETH-USDT", "gate_io", "ETH-USDT")
