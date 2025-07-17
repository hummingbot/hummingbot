#!/usr/bin/env python

import asyncio
from typing import TYPE_CHECKING

from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class ExitCommand:
    def exit(self,  # type: HummingbotApplication
             force: bool = False):
        safe_ensure_future(self.exit_loop(force), loop=self.ev_loop)

    async def exit_loop(self,  # type: HummingbotApplication
                        force: bool = False):
        if self.trading_core.strategy_task is not None and not self.trading_core.strategy_task.cancelled():
            self.trading_core.strategy_task.cancel()
        if force is False:
            success = await self.trading_core.cancel_outstanding_orders()
            if not success:
                self.notify('Wind down process terminated: Failed to cancel all outstanding orders. '
                            '\nYou may need to manually cancel remaining orders by logging into your chosen exchanges'
                            '\n\nTo force exit the app, enter "exit -f"')
                return
            # Freeze screen 1 second for better UI
            await asyncio.sleep(1)

        if self._gateway_monitor is not None:
            self._gateway_monitor.stop()

        self.notify("Winding down notifiers...")
        for notifier in self.trading_core.notifiers:
            notifier.stop()

        self.app.exit()
        self.mqtt_stop()
