import asyncio
import platform
import threading
from typing import TYPE_CHECKING

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class StopCommand:
    def stop(self,  # type: HummingbotApplication
             skip_order_cancellation: bool = False):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.stop, skip_order_cancellation)
            return
        safe_ensure_future(self.stop_loop(skip_order_cancellation), loop=self.ev_loop)

    async def stop_loop(self,  # type: HummingbotApplication
                        skip_order_cancellation: bool = False):
        self.logger().info("stop command initiated.")
        self.notify("\nWinding down...")

        # Restore App Nap on macOS.
        if platform.system() == "Darwin":
            import appnope
            appnope.nap()

        # Handle script strategy specific cleanup first
        if isinstance(self.trading_core.strategy, ScriptStrategyBase):
            await self.trading_core.strategy.on_stop()

        # Sleep two seconds to have time for order fill arrivals
        await asyncio.sleep(2.0)

        # Use trading_core encapsulated stop strategy method
        await self.trading_core.stop_strategy(skip_order_cancellation)

        # Stop the clock to halt trading operations
        await self.trading_core.stop_clock()

        # Clear application-level references
        self.market_pair = None

        self.notify("Hummingbot stopped.")
