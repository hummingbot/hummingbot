import platform
import threading
from typing import TYPE_CHECKING

from hummingbot.core.utils.async_utils import safe_ensure_future

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

        # Use trading_core shutdown method for complete cleanup
        await self.trading_core.shutdown(skip_order_cancellation)

        self.notify("Hummingbot stopped.")
