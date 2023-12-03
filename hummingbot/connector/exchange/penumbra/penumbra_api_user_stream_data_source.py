import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.penumbra import penumbra_utils as utils
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.penumbra.penumbra_exchange import PenumbraExchange


class PenumbraAPIUserStreamDataSource(UserStreamTrackerDataSource):
    def __init__(
        self,
        auth: AuthBase,
        trading_pairs: List[str],
        connector: "PenumbraExchange",
        domain: str = 'localhost:8081',
        api_factory: Optional[WebAssistantsFactory] = None,
        throttler: Optional[AsyncThrottler] = None,
    ):
        super().__init__()
        self._connector = connector
        self._auth: AuthBase = auth
        self._trading_pairs = trading_pairs
        self._last_recv_time: float = 0
        self._domain = domain
        self._throttler = throttler
        self._api_factory = api_factory or utils.build_api_factory(throttler=self._throttler, auth=self._auth)
        self._ping_interval = 0
        self._last_ws_message_sent_timestamp = 0

    # TODO: These are all stubs, unnecessary for Avellenda Strategy, implement as warranted

    async def _connected_websocket_assistant(self) -> WSAssistant:
        return

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        return

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        return

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        return
