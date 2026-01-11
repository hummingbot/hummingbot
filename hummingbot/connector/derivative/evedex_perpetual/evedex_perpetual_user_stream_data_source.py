import asyncio
from typing import TYPE_CHECKING, Optional

import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth import EvedexPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_derivative import EvedexPerpetualDerivative


class EvedexPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: EvedexPerpetualAuth,
            trading_pairs: list,
            connector: 'EvedexPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__()
        self._domain = domain
        self._api_factory = api_factory
        self._auth = auth
        self._connector = connector
        self._trading_pairs = trading_pairs

    async def _get_ws_assistant(self) -> WSAssistant:
        return await self._api_factory.get_ws_assistant()

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._get_ws_assistant()
        await ws.connect(ws_url=web_utils.wss_url(self._domain), ping_timeout=self.HEARTBEAT_TIME_INTERVAL)
        auth_payload = self._auth.get_ws_auth_payload()
        auth_request = WSJSONRequest(payload={
            "id": 1,
            "method": "auth",
            "params": auth_payload
        })
        await ws.send(auth_request)
        self.logger().info("Connected and authenticated to user stream")
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        try:
            orders_payload = {
                "id": 2,
                "method": "subscribe",
                "params": {"channel": "orders"}
            }
            positions_payload = {
                "id": 3,
                "method": "subscribe",
                "params": {"channel": "positions"}
            }
            balance_payload = {
                "id": 4,
                "method": "subscribe",
                "params": {"channel": "balance"}
            }
            await websocket_assistant.send(WSJSONRequest(payload=orders_payload))
            await websocket_assistant.send(WSJSONRequest(payload=positions_payload))
            await websocket_assistant.send(WSJSONRequest(payload=balance_payload))
            self.logger().info("Subscribed to private user stream channels")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error subscribing to user stream channels")
            raise

    async def _on_user_stream_interruption(self, websocket_assistant: Optional[WSAssistant]):
        self.logger().info("User stream interrupted. Cleaning up...")
        websocket_assistant and await websocket_assistant.disconnect()
