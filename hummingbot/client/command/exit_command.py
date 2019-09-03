#!/usr/bin/env python

import asyncio
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class ExitCommand:
    def exit(self,  # type: HummingbotApplication
             force: bool = False):
        asyncio.ensure_future(self.exit_loop(force), loop=self.ev_loop)

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
        ExchangeRateConversion.get_instance().stop()

        if force is False and self.liquidity_bounty is not None:
            self._notify("Winding down liquidity bounty submission...")
            await self.liquidity_bounty.stop_network()

        self._notify("Winding down notifiers...")
        for notifier in self.notifiers:
            notifier.stop()

        self.app.exit()
