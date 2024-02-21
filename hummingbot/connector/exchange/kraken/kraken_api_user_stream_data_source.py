import asyncio
from typing import TYPE_CHECKING, Any, Dict, Optional

from hummingbot.connector.exchange.kraken import kraken_constants as CONSTANTS
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.kraken.kraken_exchange import KrakenExchange


class KrakenAPIUserStreamDataSource(UserStreamTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 connector: 'KrakenExchange',
                 api_factory: Optional[WebAssistantsFactory] = None):

        super().__init__()
        self._api_factory = api_factory
        self._connector = connector
        self._current_auth_token: Optional[str] = None

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WS_AUTH_URL, ping_timeout=CONSTANTS.PING_TIMEOUT)
        return ws

    @property
    def last_recv_time(self):
        if self._ws_assistant is None:
            return 0
        else:
            return self._ws_assistant.last_recv_time

    async def get_auth_token(self) -> str:
        try:
            response_json = await self._connector._api_post(path_url=CONSTANTS.GET_TOKEN_PATH_URL, params={},
                                                            is_auth_required=True)
        except Exception:
            raise
        return response_json["token"]

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to order events and balance events.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:

            if self._current_auth_token is None:
                self._current_auth_token = await self.get_auth_token()

            orders_change_payload = {
                "event": "subscribe",
                "subscription": {
                    "name": "openOrders",
                    "token": self._current_auth_token
                }
            }
            subscribe_order_change_request: WSJSONRequest = WSJSONRequest(payload=orders_change_payload)

            trades_payload = {
                "event": "subscribe",
                "subscription": {
                    "name": "ownTrades",
                    "token": self._current_auth_token
                }
            }
            subscribe_trades_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)

            await websocket_assistant.send(subscribe_order_change_request)
            await websocket_assistant.send(subscribe_trades_request)

            self.logger().info("Subscribed to private order changes and trades updates channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to user streams...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if type(event_message) is list and event_message[-2] in [
            CONSTANTS.USER_TRADES_ENDPOINT_NAME,
            CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
        ]:
            queue.put_nowait(event_message)
        else:
            if event_message.get("errorMessage") is not None:
                err_msg = event_message.get("errorMessage")
                raise IOError({
                    "label": "WSS_ERROR",
                    "message": f"Error received via websocket - {err_msg}."
                })
