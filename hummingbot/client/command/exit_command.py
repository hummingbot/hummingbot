#!/usr/bin/env python

import asyncio
from typing import TYPE_CHECKING

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.strategy_v2_base import StrategyV2Base

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class ExitCommand:
    def exit(self,  # type: HummingbotApplication
             force: bool = False):
        safe_ensure_future(self.exit_loop(force), loop=self.ev_loop)

    async def exit_loop(self,  # type: HummingbotApplication
                        force: bool = False):
        # Stop strategy FIRST to prevent new orders during shutdown
        if self.trading_core.strategy and isinstance(self.trading_core.strategy, StrategyV2Base):
            await self.trading_core.strategy.on_stop()
        if self.trading_core._strategy_running:
            await self.trading_core.stop_strategy()

        if force is False:
            success = await self.trading_core.cancel_outstanding_orders()
            if not success:
                self.notify('Wind down process terminated: Failed to cancel all outstanding orders. '
                            '\nYou may need to manually cancel remaining orders by logging into your chosen exchanges'
                            '\n\nTo force exit the app, enter "exit -f"')
                return
            # Freeze screen 1 second for better UI
            await asyncio.sleep(1)

        # Stop clock to halt all remaining ticks
        if self.trading_core._is_running:
            await self.trading_core.stop_clock()

        if self.trading_core.gateway_monitor is not None:
            self.trading_core.gateway_monitor.stop_monitor()

        self.notify("Winding down notifiers...")
        for notifier in self.trading_core.notifiers:
            notifier.stop()

        self.app.exit()
        self.mqtt_stop()
