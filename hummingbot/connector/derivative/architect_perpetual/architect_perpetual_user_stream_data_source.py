import asyncio
import time
from typing import List, Optional

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.logger import HummingbotLogger


class ArchitectPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    """
    User stream data source for Architect perpetual futures.

    Subscribes to the Architect orderflow stream, which delivers:
    - Order state updates (pending, open, filled, canceled, rejected)
    - Fill events (trade executions)
    - Position changes

    The architect-py stream_orderflow() method handles the persistent
    gRPC connection automatically.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        connector,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._connector = connector
        self._domain = domain
        self._last_recv_time: float = 0

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def listen_for_user_stream(self, output: asyncio.Queue):
        while True:
            try:
                await self._run_user_stream(output)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"User stream error: {e}", exc_info=True)
                await asyncio.sleep(5.0)

    async def _run_user_stream(self, output: asyncio.Queue):
        client = self._connector._client
        if client is None:
            await asyncio.sleep(5)
            return

        venue = self._connector._execution_venue
        account = self._connector._trading_account

        self.logger().info(f"Subscribing to Architect orderflow stream (venue={venue}, account={account})")

        async for event in client.stream_orderflow(
            account=account,
            execution_venue=venue,
        ):
            self._last_recv_time = time.time()
            # Wrap event in a dict so the derivative can route by type
            await output.put({
                "type": type(event).__name__,
                "data": event,
            })
