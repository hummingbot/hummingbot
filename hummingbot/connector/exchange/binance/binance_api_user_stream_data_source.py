import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.binance import binance_constants as CONSTANTS
from hummingbot.connector.exchange.binance.binance_auth import BinanceAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange


class BinanceAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: BinanceAuth,
                 trading_pairs: List[str],
                 connector: 'BinanceExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth: BinanceAuth = auth
        self._domain = domain
        self._api_factory = api_factory
        self._connector = connector

    async def _get_ws_assistant(self) -> WSAssistant:
        return await self._api_factory.get_ws_assistant()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._get_ws_assistant()
        url = CONSTANTS.WSS_API_URL.format(self._domain)
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            params = self._auth.generate_ws_subscribe_params()
            request_id = str(uuid.uuid4())
            payload = {
                "id": request_id,
                "method": "userDataStream.subscribe.signature",
                "params": params,
            }
            subscribe_request = WSJSONRequest(payload=payload)
            await websocket_assistant.send(subscribe_request)

            response: WSResponse = await websocket_assistant.receive()
            data = response.data

            if not isinstance(data, dict) or data.get("status") != 200:
                raise IOError(f"Error subscribing to user stream (response: {data})")

            self.logger().info("Successfully subscribed to user data stream via WebSocket API")
        except IOError:
            raise
        except Exception:
            self.logger().exception("Unexpected error subscribing to user data stream")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue):
        if not isinstance(event_message, dict) or len(event_message) == 0:
            return
        # Filter out WebSocket API response messages (subscribe confirmations, etc.)
        if "id" in event_message and "status" in event_message:
            return
        # Unwrap WS API event container: {"subscriptionId": N, "event": {...}}
        if "event" in event_message and "subscriptionId" in event_message:
            event_message = event_message["event"]
        # Handle stream termination by triggering reconnect
        if event_message.get("e") == "eventStreamTerminated":
            raise ConnectionError("User data stream subscription terminated by server")
        queue.put_nowait(event_message)

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        websocket_assistant and await websocket_assistant.disconnect()
