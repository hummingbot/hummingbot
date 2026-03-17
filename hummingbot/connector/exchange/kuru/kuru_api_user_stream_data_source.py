import asyncio
import logging

from hummingbot.core.data_type.user_stream_tracker_data_source import (
    UserStreamTrackerDataSource,
)

logger = logging.getLogger(__name__)


class KuruAPIUserStreamDataSource(UserStreamTrackerDataSource):
    """
    Minimal user stream data source for Kuru DEX.

    Real order/trade events flow through the SDK's set_order_callback()
    mechanism directly into KuruExchange._user_stream_event_listener(),
    bypassing the standard UserStreamTracker pipeline.

    This class exists solely to satisfy Hummingbot's UserStreamTracker
    interface requirement.
    """

    def __init__(self, connector: "KuruExchange"):  # noqa: F821
        super().__init__()
        self._connector = connector

    @property
    def last_recv_time(self) -> float:
        """
        Returns the time of the last received event.

        The SDK handles its own WebSocket health monitoring, so we
        always report as recently active.
        """
        import time
        return time.time()

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """
        No-op. Events flow via SDK callback -> KuruExchange._sdk_order_event_queue
        -> KuruExchange._user_stream_event_listener().
        """
        await asyncio.sleep(float("inf"))

    async def _connected_websocket_assistant(self):
        """Not used - SDK manages its own WebSocket connections."""
        raise NotImplementedError("Kuru uses SDK callbacks for user events")

    async def _subscribe_channels(self, websocket_assistant):
        """Not used - SDK manages subscriptions."""
        raise NotImplementedError("Kuru uses SDK callbacks for user events")
