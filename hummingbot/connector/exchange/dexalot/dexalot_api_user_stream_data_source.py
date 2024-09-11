import asyncio
from typing import Any, Dict, Optional

from hummingbot.connector.exchange.dexalot import dexalot_constants as CONSTANTS
from hummingbot.connector.exchange.dexalot.dexalot_auth import DexalotAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger


class DexalotAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: DexalotAuth,
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth: DexalotAuth = auth
        self._domain = domain
        self._api_factory = api_factory

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_URL, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order events and balance events.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:

            user_payload = {"type": "tradereventsubscribe"}
            subscribe_order_change_request: WSJSONRequest = WSJSONRequest(payload=user_payload, is_auth_required=True)
            await websocket_assistant.send(subscribe_order_change_request)
            self.logger().info("Subscribed to private order changes and trade updates channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message.get("type") in [
            CONSTANTS.USER_TRADES_ENDPOINT_NAME,
            CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
        ]:
            queue.put_nowait(event_message)
