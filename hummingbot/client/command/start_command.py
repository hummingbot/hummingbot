#!/usr/bin/env python

import asyncio
import platform
import threading
import time
from typing import (
    Optional,
    Callable,
)

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot import init_logging
from hummingbot.client.config.in_memory_config_map import in_memory_config_map
from hummingbot.client.config.config_helpers import (
    get_strategy_starter_file,
)
from hummingbot.client.settings import (
    STRATEGIES,
)
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.data_feed.data_feed_base import DataFeedBase
from hummingbot.data_feed.coin_cap_data_feed import CoinCapDataFeed
from hummingbot.core.utils.kill_switch import KillSwitch

from typing import TYPE_CHECKING
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

        is_valid = self.status()
        if not is_valid:
            return

        strategy_file_path = in_memory_config_map.get("strategy_file_path").value
        init_logging("hummingbot_logs.yml",
                     override_log_level=log_level.upper() if log_level else None,
                     strategy_file_path=strategy_file_path)

        # If macOS, disable App Nap.
        if platform.system() == "Darwin":
            import appnope
            appnope.nope()

        # TODO add option to select data feed
        self.data_feed: DataFeedBase = CoinCapDataFeed.get_instance()

        self._initialize_notifiers()

        ExchangeRateConversion.get_instance().start()
        strategy_name = in_memory_config_map.get("strategy").value
        self._notify(f"\n  Status check complete. Starting '{strategy_name}' strategy...")
        safe_ensure_future(self.start_market_making(strategy_name), loop=self.ev_loop)

    async def start_market_making(self,  # type: HummingbotApplication
                                  strategy_name: str):
        await ExchangeRateConversion.get_instance().ready_notifier.wait()

        start_strategy: Callable = get_strategy_starter_file(strategy_name)
        if strategy_name in STRATEGIES:
            start_strategy(self)
        else:
            raise NotImplementedError

        try:
            config_path: str = in_memory_config_map.get("strategy_file_path").value
            self.start_time = time.time() * 1e3  # Time in milliseconds
            self.clock = Clock(ClockMode.REALTIME)
            if self.wallet is not None:
                self.clock.add_iterator(self.wallet)
            for market in self.markets.values():
                if market is not None:
                    self.clock.add_iterator(market)
                    self.markets_recorder.restore_market_states(config_path, market)
                    if len(market.limit_orders) > 0:
                        self._notify(f"  Cancelling dangling limit orders on {market.name}...")
                        await market.cancel_all(5.0)
            if self.strategy:
                self.clock.add_iterator(self.strategy)
            self.strategy_task: asyncio.Task = safe_ensure_future(self._run_clock(), loop=self.ev_loop)
            self._notify(f"\n  '{strategy_name}' strategy started.\n"
                         f"  You can use the `status` command to query the progress.")

            if not self.starting_balances:
                self.starting_balances = await self.wait_till_ready(self.balance_snapshot)

            if self._trading_required:
                self.kill_switch = KillSwitch(self)
                await self.wait_till_ready(self.kill_switch.start)
        except Exception as e:
            self.logger().error(str(e), exc_info=True)
