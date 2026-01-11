import asyncio
from typing import TYPE_CHECKING, Optional

import hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_auth import AevoPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_derivative import AevoPerpetualDerivative


class AevoPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: AevoPerpetualAuth,
            connector: 'AevoPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._connector = connector
        self._ws_assistant: Optional[WSAssistant] = None

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._get_ws_assistant()
        url = web_utils.wss_url(self._domain)
        await ws.connect(ws_url=url, ping_timeout=self.HEARTBEAT_TIME_INTERVAL)

        auth_payload = self._auth.get_ws_auth_payload()
        auth_request = WSJSONRequest(payload=auth_payload)
        await ws.send(auth_request)

        self.logger().info("Successfully connected and authenticated to user stream")
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            orders_payload = {
                "op": "subscribe",
                "data": ["orders"]
            }
            subscribe_orders = WSJSONRequest(payload=orders_payload)
            await websocket_assistant.send(subscribe_orders)

            fills_payload = {
                "op": "subscribe",
                "data": ["fills"]
            }
            subscribe_fills = WSJSONRequest(payload=fills_payload)
            await websocket_assistant.send(subscribe_fills)

            positions_payload = {
                "op": "subscribe",
                "data": ["positions"]
            }
            subscribe_positions = WSJSONRequest(payload=positions_payload)
            await websocket_assistant.send(subscribe_positions)

            self.logger().info("Subscribed to private order, fill, and position channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        self._ws_assistant = None
        if websocket_assistant:
            await websocket_assistant.disconnect()
