"""User stream data source for Limitless.

Limitless order/fill updates are polled via REST in the main exchange class.
This data source keeps the Hummingbot interface happy with a no-op polling
loop that never fails (so the connector reports ready).
"""

import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.limitless import limitless_constants as CONSTANTS
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.limitless.limitless_exchange import LimitlessExchange


class LimitlessAPIUserStreamDataSource(UserStreamTrackerDataSource):
    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800
    HEARTBEAT_TIME_INTERVAL = 30.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: AuthBase,
        trading_pairs: List[str],
        connector: "LimitlessExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._connector = connector
        self._trading_pairs = trading_pairs
        self._last_recv_time = time.time()

    @property
    def last_recv_time(self) -> float:
        return self._last_recv_time

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """Not used — user updates handled via REST polling in exchange class."""
        raise NotImplementedError("LimitlessAPIUserStreamDataSource uses polling, not WS")

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """Not used."""
        pass

    async def listen_for_user_stream(self, output: asyncio.Queue):
        """Override parent's WS-based listener with a keep-alive loop.

        The inner connector handles order/fill tracking via REST polling.
        This loop just keeps the user stream tracker alive so the connector
        reports ready.
        """
        while True:
            try:
                self._last_recv_time = time.time()
                await asyncio.sleep(self.HEARTBEAT_TIME_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().warning(
                    "Unexpected error in user stream keep-alive. Retrying...",
                    exc_info=True,
                )
                await asyncio.sleep(5.0)

    async def _process_event_message(
        self, event_message: Dict[str, Any], queue: asyncio.Queue
    ):
        pass
