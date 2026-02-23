import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.grvt_perpetual import (
    grvt_perpetual_constants as CONSTANTS,
    grvt_perpetual_web_utils as web_utils,
)
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GRVTPerpetualAuth


class GRVTPerpetualUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: "GRVTPerpetualAuth",
        trading_pairs: List[str],
        connector_name: str,
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(auth, trading_pairs, connector_name)
        self._auth = auth
        self._api_factory = api_factory
        self._domain = domain

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws_url = CONSTANTS.PROD_TRADE_WS_URL if self._domain == CONSTANTS.DOMAIN else CONSTANTS.TESTNET_TRADE_WS_URL
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=ws_url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            subscribe_payload = {
                "type": "subscribe",
                "channel": "user_trade",
                "subAccountID": self._auth._sub_account_id
            }
            await ws.send(WSJSONRequest(payload=subscribe_payload))

            subscribe_payload_orders = {
                "type": "subscribe",
                "channel": "order",
                "subAccountID": self._auth._sub_account_id
            }
            await ws.send(WSJSONRequest(payload=subscribe_payload_orders))
            
            subscribe_payload_positions = {
                "type": "subscribe",
                "channel": "position",
                "subAccountID": self._auth._sub_account_id
            }
            await ws.send(WSJSONRequest(payload=subscribe_payload_positions))

            self.logger().info("Subscribed to user channels.")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error subscribing to user stream.", exc_info=True)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if len(event_message) > 0:
            queue.put_nowait(event_message)
