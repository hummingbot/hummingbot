"""User stream data source for Limitless.

Limitless does not currently provide a user-specific WebSocket stream.
Order/fill updates are handled via REST polling in the main exchange class.
This data source satisfies the Hummingbot interface with a minimal
polling-based implementation.
"""

import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.limitless import limitless_constants as CONSTANTS, limitless_web_utils as web_utils
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
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
        self._ws_assistants: List[WSAssistant] = []

    @property
    def last_recv_time(self) -> float:
        if self._ws_assistant:
            return self._ws_assistant.last_recv_time
        return 0

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._get_ws_assistant()
        url = web_utils.wss_url(self._domain)
        await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """No user-specific WS channels on Limitless yet; keep connection alive."""
        try:
            ping_payload = {"method": "ping"}
            ping_request = WSJSONRequest(payload=ping_payload)
            await websocket_assistant.send(ping_request)
            self.logger().info("User stream WS connected (polling mode)...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error subscribing to user streams...")
            raise

    async def _process_event_message(
        self, event_message: Dict[str, Any], queue: asyncio.Queue
    ):
        if event_message.get("error") is not None:
            err_msg = event_message.get("error", {}).get("message", event_message.get("error"))
            raise IOError({"label": "WSS_ERROR", "message": f"Error received via websocket - {err_msg}."})

    async def _process_websocket_messages(
        self, websocket_assistant: WSAssistant, queue: asyncio.Queue
    ):
        while True:
            try:
                await super()._process_websocket_messages(
                    websocket_assistant=websocket_assistant, queue=queue
                )
            except asyncio.TimeoutError:
                ping_request = WSJSONRequest(payload={"method": "ping"})
                await websocket_assistant.send(ping_request)
