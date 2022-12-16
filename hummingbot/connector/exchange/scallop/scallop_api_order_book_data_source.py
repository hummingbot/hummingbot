import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.scallop import scallop_constants as CONSTANTS, scallop_web_utils as web_utils
from hummingbot.connector.exchange.scallop.scallop_order_book import ScallopOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.scallop.scallop_exchange import ScallopExchange


class ScallopAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'ScallopExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        params = {
            "symbol": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "limit": "100"
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL,
        )

        return data

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
           for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

                trades_payload = {
                    "event":"sub",
                    "params":{
                        "channel": f"market_{symbol}_trade_ticker",
                    }
                }
                subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)

                order_book_payload = {
                    "event":"sub",
                    "params":{
                        "channel": f"market_{symbol}_depth_step0",
                    }
                }
                subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=order_book_payload)

                await ws.send(subscribe_trade_request)
                await ws.send(subscribe_orderbook_request)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_URL,
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = ScallopOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        symbol = raw_message["channel"].split("_")[1]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
        trade_timestamp: float = raw_message['ts'] * 1e-3
        trade_message = ScallopOrderBook.trade_message_from_exchange(
            raw_message, trade_timestamp, {"trading_pair": trading_pair})
        message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        symbol = raw_message["channel"].split("_")[1]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
        diff_timestamp: float = raw_message['ts'] * 1e-3
        order_book_message: OrderBookMessage = ScallopOrderBook.diff_message_from_exchange(
            raw_message, diff_timestamp, {"trading_pair": trading_pair})
        message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "tick" in event_message:
            event_channel = event_message.get("channel")
            channel = (self._diff_messages_queue_key if event_channel.endswith(CONSTANTS.SNAPSHOT_CHANNEL_SUFFIX)
                       else self._trade_messages_queue_key)
        return channel
