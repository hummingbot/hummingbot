import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.bitstamp import bitstamp_constants as CONSTANTS, bitstamp_web_utils as web_utils
from hummingbot.connector.exchange.bitstamp.bitstamp_auth import BitstampAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bitstamp.bitstamp_exchange import BitstampExchange


class BitstampAPIUserStreamDataSource(UserStreamTrackerDataSource):
    USER_STREAM_EVENTS = {
        CONSTANTS.USER_ORDER_CREATED,
        CONSTANTS.USER_ORDER_CHANGED,
        CONSTANTS.USER_ORDER_DELETED,
        CONSTANTS.USER_TRADE,
        CONSTANTS.USER_SELF_TRADE,
    }

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 auth: BitstampAuth,
                 trading_pairs: List[str],
                 connector: 'BitstampExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__()
        self._auth: BitstampAuth = auth
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._current_listen_key = None
        self._domain = domain
        self._api_factory = api_factory

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_URL.format(self._domain),
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        Bitstamp does not require any channel subscription.

        :param websocket_assistant: the websocket assistant used to connect to the exchange
        """
        try:

            rest_assistant = await self._api_factory.get_rest_assistant()
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

                resp = await rest_assistant.execute_request(
                    url=web_utils.private_rest_url(path_url=CONSTANTS.WEBSOCKET_TOKEN_URL, domain=self._domain),
                    method=RESTMethod.POST,
                    is_auth_required=True,
                    throttler_limit_id=CONSTANTS.WEBSOCKET_TOKEN_URL
                )
                user_id = resp.get("user_id")
                token = resp.get("token")

                payload = {
                    "event": "bts:subscribe",
                    "data": {
                        "channel": CONSTANTS.WS_PRIVATE_MY_TRADES.format(symbol, user_id),
                        "auth": token
                    }
                }
                my_trades_subscribe_request: WSJSONRequest = WSJSONRequest(payload=payload)

                payload = {
                    "event": "bts:subscribe",
                    "data": {
                        "channel": CONSTANTS.WS_PRIVATE_MY_SELF_TRADES.format(symbol, user_id),
                        "auth": token
                    }
                }
                my_self_trades_subscribe_request: WSJSONRequest = WSJSONRequest(payload=payload)

                payload = {
                    "event": "bts:subscribe",
                    "data": {
                        "channel": CONSTANTS.WS_PRIVATE_MY_ORDERS.format(symbol, user_id),
                        "auth": token
                    }
                }
                my_orders_subscribe_request: WSJSONRequest = WSJSONRequest(payload=payload)

                await websocket_assistant.send(my_trades_subscribe_request)
                await websocket_assistant.send(my_self_trades_subscribe_request)
                await websocket_assistant.send(my_orders_subscribe_request)

                self.logger().info("Subscribed to private account and orders channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book trading...")
            raise

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        if len(event_message) > 0:
            event = event_message.get("event", "")
            channel = event_message.get("channel", "")

            if event in self.USER_STREAM_EVENTS:
                queue.put_nowait(event_message)
            else:
                if event == "bts:subscription_succeeded":
                    self.logger().info(f"Successfully subscribed to '{channel}'...")
                elif event == "bts:request_reconnect":
                    raise ConnectionError("Received request to reconnect. Reconnecting...")
                else:
                    self.logger().debug(f"Received unknown event message: {event_message}")
