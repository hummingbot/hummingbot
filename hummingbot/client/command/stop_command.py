import platform
from hummingbot.core.utils.async_utils import safe_ensure_future
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class StopCommand:
    def stop(self,  # type: HummingbotApplication
             skip_order_cancellation: bool = False):
        safe_ensure_future(self.stop_loop(skip_order_cancellation), loop=self.ev_loop)

    async def stop_loop(self,  # type: HummingbotApplication
                        skip_order_cancellation: bool = False):
        self.logger().info("stop command initiated.")
        self._notify("\nWinding down...")

        # Restore App Nap on macOS.
        if platform.system() == "Darwin":
            import appnope
            appnope.nap()

        if self._script_iterator is not None:
            self._script_iterator.stop(self.clock)

        if self._trading_required and not skip_order_cancellation:
            # Remove the strategy from clock before cancelling orders, to
            # prevent race condition where the strategy tries to create more
            # orders during cancellation.
            if self.clock:
                self.clock.remove_iterator(self.strategy)
            success = await self._cancel_outstanding_orders()
            if success:
                # Only erase markets when cancellation has been successful
                self.markets = {}

        if self.strategy_task is not None and not self.strategy_task.cancelled():
            self.strategy_task.cancel()

        if self.markets_recorder is not None:
            self.markets_recorder.stop()

        if self.kill_switch is not None:
            self.kill_switch.stop()

        self.wallet = None
        self.strategy_task = None
        self.strategy = None
        self.market_pair = None
        self.clock = None
        self.markets_recorder = None
