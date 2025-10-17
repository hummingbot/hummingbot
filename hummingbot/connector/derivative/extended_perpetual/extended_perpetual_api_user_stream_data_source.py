import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.extended_perpetual import extended_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.extended_perpetual import extended_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.extended_perpetual.extended_perpetual_auth import ExtendedPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.extended_perpetual.extended_perpetual_derivative import ExtendedPerpetualDerivative


class ExtendedPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: ExtendedPerpetualAuth,
        trading_pairs: List[str],
        connector: "ExtendedPerpetualDerivative",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._extended_auth: ExtendedPerpetualAuth = auth
        self._api_factory = api_factory
        self._trading_pairs = trading_pairs or []
        self._connector = connector
        self._domain = domain
        self._last_ws_message_sent_timestamp = 0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates and connects to an authenticated websocket for Extended
        Extended uses: /stream.extended.exchange/v1/account for account updates
        """
        # Get authentication headers
        headers = self._extended_auth.get_auth_headers()
        
        # Build account updates WebSocket URL
        ws_base = web_utils.wss_url(domain=self._domain)
        ws_url = f"{ws_base}/stream.extended.exchange/v1/account"
        
        self.logger().info(f"🔌 Connecting to Extended account WebSocket: {ws_url}")
        self.logger().info(f"🔌 Auth headers: {list(headers.keys())}")
        
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ws_headers=headers)
        
        self.logger().info(f"✅ Account WebSocket connected successfully")
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to account update events.
        """
        try:
            # Subscribe to account updates (orders, positions, balance)
            payload = {
                "type": "subscribe",
                "channel": CONSTANTS.USER_ORDERS_ENDPOINT_NAME
            }
            subscribe_request: WSJSONRequest = WSJSONRequest(payload)

            await websocket_assistant.send(subscribe_request)

            self._last_ws_message_sent_timestamp = self._time()
            self.logger().info("Subscribed to private account updates channel...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        """
        Process incoming websocket messages
        """
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            if data is not None:  # data will be None when the websocket is disconnected
                await self._process_event_message(
                    event_message=data, queue=queue, websocket_assistant=websocket_assistant
                )

    async def _process_event_message(
        self, event_message: Dict[str, Any], queue: asyncio.Queue, websocket_assistant: WSAssistant
    ):
        """
        Process individual event messages from Extended websocket
        """
        # Check if event_message is a dictionary before calling .get()
        if not isinstance(event_message, dict):
            return
            
        if len(event_message) > 0:
            message_type = event_message.get("type", "")
            channel = event_message.get("channel", "")
            
            # Handle ping/pong
            if message_type == "ping":
                pong_payload = {"type": "pong"}
                pong_request = WSJSONRequest(payload=pong_payload)
                await websocket_assistant.send(request=pong_request)
            
            # Handle account updates
            elif channel == CONSTANTS.USER_ORDERS_ENDPOINT_NAME:
                # Extended sends order updates, position updates, and balance updates
                # through the account updates channel
                queue.put_nowait(event_message)

    def _time(self) -> float:
        """Get current time"""
        import time
        return time.time()

