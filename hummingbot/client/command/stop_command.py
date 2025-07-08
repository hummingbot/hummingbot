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
        if self.trading_core.strategy and isinstance(self.trading_core.strategy, ScriptStrategyBase):
            await self.trading_core.strategy.on_stop()

        # Stop strategy if running
        if self.trading_core._strategy_running:
            await self.trading_core.stop_strategy()

        # Cancel outstanding orders
        if not skip_order_cancellation:
            await self.trading_core.cancel_outstanding_orders()

        # Remove all connectors
        connector_names = list(self.trading_core.connectors.keys())
        for name in connector_names:
            try:
                self.trading_core.remove_connector(name)
            except Exception as e:
                self.logger().error(f"Error stopping connector {name}: {e}")

        # Stop clock if running
        if self.trading_core._is_running:
            await self.trading_core.stop_clock()

        # Stop markets recorder
        if self.trading_core.markets_recorder:
            self.trading_core.markets_recorder.stop()
            self.trading_core.markets_recorder = None

        # Clear strategy references
        self.trading_core.strategy = None
        self.trading_core.strategy_name = None
        self.trading_core.strategy_config_map = None
        self.trading_core._strategy_file_name = None
        self.trading_core._config_source = None
        self.trading_core._config_data = None

        self.notify("Hummingbot stopped.")
