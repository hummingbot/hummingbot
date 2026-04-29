import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS, gemini_web_utils as web_utils
from hummingbot.connector.exchange.gemini.gemini_auth import GeminiAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.gemini.gemini_exchange import GeminiExchange


class GeminiAPIUserStreamDataSource(UserStreamTrackerDataSource):

    HEARTBEAT_TIME_INTERVAL = 30.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: AuthBase,
                 trading_pairs: List[str],
                 connector: 'GeminiExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth: GeminiAuth = auth
        self._domain = domain
        self._api_factory = api_factory
        self._connector = connector

    async def _get_ws_assistant(self) -> WSAssistant:
        return await self._api_factory.get_ws_assistant()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._get_ws_assistant()
        auth_headers = self._auth.generate_ws_auth_headers()
        url = web_utils.wss_order_events_url(domain=self._domain)
        await ws.connect(
            ws_url=url,
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
            ws_headers=auth_headers)
        self.logger().info("Successfully connected to Gemini order events stream")
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        # Gemini order events endpoint auto-subscribes to all order events on authenticated connect.
        # No subscription message is needed.
        self.logger().info("Subscribed to private order events channel...")

    async def _process_event_message(self, event_message, queue: asyncio.Queue):
        if isinstance(event_message, list):
            # Initial snapshot of open orders sent as a list on (re)connect.
            # Gemini marks these with type "initial".
            for order_event in event_message:
                if isinstance(order_event, dict) and order_event.get("type") in (
                    "initial", "accepted", "booked"
                ):
                    queue.put_nowait(order_event)
            return
        msg_type = event_message.get("type", "")
        if msg_type in ("heartbeat", "subscription_ack"):
            return
        if msg_type in (
            "initial", "accepted", "rejected", "booked",
            "fill", "cancelled", "closed", "cancel_rejected"
        ):
            queue.put_nowait(event_message)

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        websocket_assistant and await websocket_assistant.disconnect()
