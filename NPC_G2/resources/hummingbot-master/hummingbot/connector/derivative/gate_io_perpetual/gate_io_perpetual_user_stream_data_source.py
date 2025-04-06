import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.derivative.gate_io_perpetual import gate_io_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_auth import GateIoPerpetualAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_derivative import GateIoPerpetualExchange


class GateIoPerpetualAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: GateIoPerpetualAuth,
                 user_id: str,
                 trading_pairs: List[str],
                 connector: 'GateIoPerpetualExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._api_factory = api_factory
        self._auth: GateIoPerpetualAuth = auth
        self._user_id = user_id
        self._trading_pairs: List[str] = trading_pairs
        self._connector = connector

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WS_URL, ping_timeout=CONSTANTS.PING_TIMEOUT)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order events.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:
            user_info_symbols = [self._user_id]
            symbols = ["!all"]
            user_info_symbols.extend(symbols)
            orders_change_payload = {
                "time": int(self._time()),
                "channel": CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
                "event": "subscribe",
                "payload": user_info_symbols
            }
            subscribe_order_change_request: WSJSONRequest = WSJSONRequest(
                payload=orders_change_payload,
                is_auth_required=True)

            trades_payload = {
                "time": int(self._time()),
                "channel": CONSTANTS.USER_TRADES_ENDPOINT_NAME,
                "event": "subscribe",
                "payload": user_info_symbols
            }
            subscribe_trades_request: WSJSONRequest = WSJSONRequest(
                payload=trades_payload,
                is_auth_required=True)
            positions_payload = {
                "time": int(self._time()),
                "channel": CONSTANTS.USER_POSITIONS_ENDPOINT_NAME,
                "event": "subscribe",
                "payload": user_info_symbols
            }
            subscribe_positions_request: WSJSONRequest = WSJSONRequest(
                payload=positions_payload,
                is_auth_required=True)
            await websocket_assistant.send(subscribe_order_change_request)
            await websocket_assistant.send(subscribe_trades_request)
            await websocket_assistant.send(subscribe_positions_request)

            self.logger().info("Subscribed to private order changes channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if event_message.get("error") is not None:
            err_msg = event_message.get("error", {}).get("message", event_message.get("error"))
            raise IOError({
                "label": "WSS_ERROR",
                "message": f"Error received via websocket - {err_msg}."
            })
        elif event_message.get("event") == "update" and event_message.get("channel") in [
            CONSTANTS.USER_TRADES_ENDPOINT_NAME,
            CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
            CONSTANTS.USER_POSITIONS_ENDPOINT_NAME,
            CONSTANTS.TICKER_ENDPOINT_NAME,
        ]:
            queue.put_nowait(event_message)
