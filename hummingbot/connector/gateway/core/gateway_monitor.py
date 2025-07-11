"""
Gateway service monitor.
"""
import asyncio
import logging
from enum import Enum
from typing import TYPE_CHECKING, Callable, List, Optional

from hummingbot.logger import HummingbotLogger

from .gateway_client import GatewayClient

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class GatewayStatus(Enum):
    """Gateway connection status."""
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class GatewayMonitor:
    """
    Monitors Gateway service availability and triggers callbacks.
    Also provides backward compatibility with GatewayStatusMonitor.
    """

    _logger: Optional[HummingbotLogger] = None

    # Events - using integer enum values like other event systems
    GATEWAY_STATUS_UPDATE = 91

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(
        self,
        app_or_client,
        check_interval: float = 2.0,
        max_check_interval: float = 60.0
    ):
        """
        Initialize Gateway monitor.

        :param app_or_client: HummingbotApplication or GatewayClient instance
        :param check_interval: Interval between checks in seconds
        """

        # Support both old (app) and new (client) initialization
        if hasattr(app_or_client, 'client_config_map'):
            # Old style - HummingbotApplication passed
            self._app = app_or_client
            # Pass the client_config_map instead of base_url
            self.client = GatewayClient.get_instance(self._app.client_config_map)
        else:
            # New style - GatewayClient passed
            self._app = None
            self.client = app_or_client

        self.check_interval = check_interval
        self._base_check_interval = check_interval
        self._max_check_interval = max_check_interval
        self._consecutive_failures = 0
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_available = False
        self._gateway_status = GatewayStatus.OFFLINE
        self._was_ever_online = False  # Track if gateway was ever online
        self._on_available_callback: Optional[Callable] = None
        self._on_unavailable_callback: Optional[Callable] = None

        # Additional attributes for compatibility
        self._ready_event = asyncio.Event()
        self.gateway_config_keys: List[str] = []

    @property
    def is_available(self) -> bool:
        """Check if Gateway is available."""
        return self._is_available

    @property
    def gateway_status(self) -> GatewayStatus:
        """Get current gateway status."""
        return self._gateway_status

    @property
    def ready_event(self) -> asyncio.Event:
        """Event that signals when gateway is ready."""
        return self._ready_event

    def set_callbacks(
        self,
        on_available: Optional[Callable] = None,
        on_unavailable: Optional[Callable] = None
    ):
        """
        Set callbacks for availability changes.

        :param on_available: Called when Gateway becomes available
        :param on_unavailable: Called when Gateway becomes unavailable
        """
        self._on_available_callback = on_available
        self._on_unavailable_callback = on_unavailable

    async def start(self):
        """Start monitoring Gateway."""
        if self._running:
            return

        # Check if gateway is available on startup
        try:
            is_online = await self.client.ping_gateway()
            if is_online:
                self._was_ever_online = True
                self._is_available = True
                self._gateway_status = GatewayStatus.ONLINE
                self.logger().info("Gateway Service is ONLINE.")
                # Initialize gateway caches
                try:
                    await self.client.initialize_gateway()
                except Exception as e:
                    self.logger().warning(f"Failed to initialize gateway: {e}")
                self._ready_event.set()

                # Start monitoring since gateway is available
                self._running = True
                self._monitor_task = asyncio.create_task(self._monitor_loop())
                self.logger().info("Gateway monitor started")
            else:
                # Gateway is offline, don't start monitoring
                self.logger().info("Gateway is offline. Monitoring will not start.")
        except Exception:
            # Gateway is not available, don't start monitoring
            self.logger().info("Gateway is not available. Monitoring will not start.")

    async def stop(self):
        """Stop monitoring Gateway."""
        self._running = False

        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        self.logger().info("Gateway monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop with exponential backoff."""
        while self._running:
            try:
                # Check Gateway status
                is_online = await self.client.ping_gateway()

                # Handle status change
                if is_online != self._is_available:
                    self._is_available = is_online
                    old_status = self._gateway_status
                    self._gateway_status = GatewayStatus.ONLINE if is_online else GatewayStatus.OFFLINE

                    if is_online:
                        # Reset backoff on successful connection
                        self._consecutive_failures = 0
                        self.check_interval = self._base_check_interval
                        self._was_ever_online = True

                        if old_status == GatewayStatus.OFFLINE:
                            self.logger().info("Gateway Service is ONLINE.")
                            # Initialize gateway caches when it comes online
                            try:
                                await self.client.initialize_gateway()
                            except Exception as e:
                                self.logger().warning(f"Failed to initialize gateway: {e}")
                        self._ready_event.set()

                        if self._on_available_callback:
                            await self._on_available_callback()
                    else:
                        if old_status == GatewayStatus.ONLINE:
                            self.logger().info("Connection to Gateway container lost...")
                        self._ready_event.clear()
                        if self._on_unavailable_callback:
                            await self._on_unavailable_callback()
                else:
                    # If already online, reset failure counter
                    if is_online:
                        self._consecutive_failures = 0
                        self.check_interval = self._base_check_interval

            except Exception:
                # Gateway is unavailable
                # Only continue monitoring if gateway was previously online
                if not self._was_ever_online:
                    # Gateway was never online, stop monitoring
                    self.logger().info("Gateway was never available. Stopping monitor.")
                    self._running = False
                    break

                self._consecutive_failures += 1

                # Apply exponential backoff
                self.check_interval = min(
                    self._base_check_interval * (2 ** min(self._consecutive_failures - 1, 5)),
                    self._max_check_interval
                )

                # Only log connection lost once when transitioning from online to offline
                if self._is_available:
                    self._is_available = False
                    old_status = self._gateway_status
                    self._gateway_status = GatewayStatus.OFFLINE
                    if old_status == GatewayStatus.ONLINE:
                        self.logger().info("Connection to Gateway container lost...")
                    self._ready_event.clear()

                    if self._on_unavailable_callback:
                        try:
                            await self._on_unavailable_callback()
                        except Exception as callback_error:
                            self.logger().error(f"Error in unavailable callback: {callback_error}")
                elif self._consecutive_failures == 10:
                    # Log a reminder after 10 consecutive failures
                    self.logger().info(f"Gateway still offline. Checking every {self.check_interval}s (max {self._max_check_interval}s)")

            # Wait before next check
            await asyncio.sleep(self.check_interval)

    async def check_once(self) -> bool:
        """
        Check Gateway availability once.

        :return: True if available
        """
        try:
            return await self.client.ping_gateway()
        except Exception:
            return False
