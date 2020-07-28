#!/usr/bin/env python

import asyncio
import platform
import threading
import time
from typing import (
    Optional,
    Callable,
)
from os.path import dirname
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot import init_logging
from hummingbot.client.config.config_helpers import (
    get_strategy_starter_file,
)
from hummingbot.client.settings import (
    STRATEGIES,
    SCRIPTS_PATH
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.data_feed.coin_cap_data_feed import CoinCapDataFeed
from hummingbot.core.utils.kill_switch import KillSwitch
from typing import TYPE_CHECKING
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.script.script_iterator import ScriptIterator
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class StartCommand:
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
              log_level: Optional[str] = None):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.start, log_level)
            return
        safe_ensure_future(self.start_check(log_level), loop=self.ev_loop)

    async def start_check(self,  # type: HummingbotApplication
                          log_level: Optional[str] = None):

        if self.strategy_task is not None and not self.strategy_task.done():
            self._notify('The bot is already running - please run "stop" first')
            return

        is_valid = await self.status_check_all(notify_success=False)
        if not is_valid:
            return

        init_logging("hummingbot_logs.yml",
                     override_log_level=log_level.upper() if log_level else None,
                     strategy_file_path=self.strategy_file_name)

        # If macOS, disable App Nap.
        if platform.system() == "Darwin":
            import appnope
            appnope.nope()

        # TODO add option to select data feed
        self.data_feed: DataFeedBase = CoinCapDataFeed.get_instance()

        self._initialize_notifiers()

        self._notify(f"\nStatus check complete. Starting '{self.strategy_name}' strategy...")
        if global_config_map.get("paper_trade_enabled").value:
            self._notify("\nPaper Trading ON: All orders are simulated, and no real orders are placed.")
        await self.start_market_making(self.strategy_name)

    async def start_market_making(self,  # type: HummingbotApplication
                                  strategy_name: str):
        start_strategy: Callable = get_strategy_starter_file(strategy_name)
        if strategy_name in STRATEGIES:
            start_strategy(self)
        else:
            raise NotImplementedError

        try:
            config_path: str = self.strategy_file_name
            self.start_time = time.time() * 1e3  # Time in milliseconds
            self.clock = Clock(ClockMode.REALTIME)
            if self.wallet is not None:
                self.clock.add_iterator(self.wallet)
            for market in self.markets.values():
                if market is not None:
                    self.clock.add_iterator(market)
                    self.markets_recorder.restore_market_states(config_path, market)
                    if len(market.limit_orders) > 0:
                        self._notify(f"Cancelling dangling limit orders on {market.name}...")
                        await market.cancel_all(5.0)
            if self.strategy:
                self.clock.add_iterator(self.strategy)
            if global_config_map["script_enabled"].value:
                script_file = global_config_map["script_file_path"].value
                folder = dirname(script_file)
                if folder == "":
                    script_file = SCRIPTS_PATH + script_file
                if self.strategy_name != "pure_market_making":
                    self._notify("Error: script feature is only available for pure_market_making strategy (for now).")
                else:
                    self._script_iterator = ScriptIterator(script_file, list(self.markets.values()),
                                                           self.strategy, 0.1)
                    self.clock.add_iterator(self._script_iterator)
                    self._notify(f"Script ({script_file}) started.")

            self.strategy_task: asyncio.Task = safe_ensure_future(self._run_clock(), loop=self.ev_loop)
            self._notify(f"\n'{strategy_name}' strategy started.\n"
                         f"Run `status` command to query the progress.")
            self.logger().info("start command initiated.")
            if not self.starting_balances:
                self.starting_balances = await self.wait_till_ready(self.balance_snapshot)

            if self._trading_required:
                self.kill_switch = KillSwitch(self)
                await self.wait_till_ready(self.kill_switch.start)
        except Exception as e:
            self.logger().error(str(e), exc_info=True)
