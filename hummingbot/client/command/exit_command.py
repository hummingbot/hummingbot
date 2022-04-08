#!/usr/bin/env python

import asyncio
from hummingbot.core.utils.async_utils import safe_ensure_future

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class ExitCommand:
    def exit(self,  # type: HummingbotApplication
             force: bool = False):
        safe_ensure_future(self.exit_loop(force), loop=self.ev_loop)

    async def exit_loop(self,  # type: HummingbotApplication
                        force: bool = False):
        if self.strategy_task is not None and not self.strategy_task.cancelled():
            self.strategy_task.cancel()
        if force is False and self._trading_required:
            success = await self._cancel_outstanding_orders()
            if not success:
                self._notify('Wind down process terminated: Failed to cancel all outstanding orders. '
                             '\nYou may need to manually cancel remaining orders by logging into your chosen exchanges'
                             '\n\nTo force exit the app, enter "exit -f"')
                return
            # Freeze screen 1 second for better UI
            await asyncio.sleep(1)

        self._notify("Winding down notifiers...")
        for notifier in self.notifiers:
            notifier.stop()

        self.app.exit()
