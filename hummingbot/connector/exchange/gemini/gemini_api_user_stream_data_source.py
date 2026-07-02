import asyncio
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS, gemini_web_utils as web_utils
from hummingbot.connector.exchange.gemini.gemini_auth import GeminiAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.gemini.gemini_exchange import GeminiExchange


class GeminiAPIUserStreamDataSource(UserStreamTrackerDataSource):

    HEARTBEAT_TIME_INTERVAL = 30.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: GeminiAuth,
                 trading_pairs: List[str],
                 connector: 'GeminiExchange',
                 api_factory: WebAssistantsFactory):
        super().__init__()
        self._auth: GeminiAuth = auth
        self._api_factory = api_factory
        self._connector = connector
        self._trading_pairs = trading_pairs

    async def _get_ws_assistant(self) -> WSAssistant:
        return await self._api_factory.get_ws_assistant()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates a WebSocket connection to the Gemini Fast API with authentication headers.
        Authentication is done during the WebSocket handshake via headers.
        """
        ws = await self._get_ws_assistant()
        auth_headers = self._auth.get_ws_auth_headers()
        await ws.connect(
            ws_url=web_utils.wss_url(),
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
            ws_headers=auth_headers,
        )
        self.logger().info("Successfully connected to authenticated user stream")
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order events and balance update channels via the Fast API.
        """
        try:
            # Subscribe to order events
            payload = {
                "id": "user_orders",
                "method": CONSTANTS.WS_METHOD_SUBSCRIBE,
                "params": [CONSTANTS.WS_ORDER_EVENTS_STREAM]
            }
            subscribe_orders_request: WSJSONRequest = WSJSONRequest(payload=payload)
            await websocket_assistant.send(subscribe_orders_request)

            # Subscribe to balance updates
            payload = {
                "id": "user_balances",
                "method": CONSTANTS.WS_METHOD_SUBSCRIBE,
                "params": [CONSTANTS.WS_BALANCE_STREAM]
            }
            subscribe_balances_request: WSJSONRequest = WSJSONRequest(payload=payload)
            await websocket_assistant.send(subscribe_balances_request)

            self.logger().info("Subscribed to user order events and balance update channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to user stream channels...",
                exc_info=True
            )
            raise

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        self.logger().info("User stream interrupted. Cleaning up...")
        websocket_assistant and await websocket_assistant.disconnect()
