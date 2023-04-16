import asyncio
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.hotbit import hotbit_constants as CONSTANTS, hotbit_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.hotbit.hotbit_exchange import HotbitExchange


class HotbitAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'HotbitExchange',
                 api_factory: WebAssistantsFactory
                 ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._trading_pairs: List[str] = trading_pairs

        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str]) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_data = snapshot_response["result"]
        snapshot_timestamp: float = self._time()
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": snapshot_response["id"],
                "bids": snapshot_data["bids"],
                "asks": snapshot_data["asks"],
            },
            timestamp=snapshot_timestamp)
        return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        params = {
            "market": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "interval": CONSTANTS.DEPTH_PRICE_INTERVAL,
            "limit": CONSTANTS.DEPTH_MAX_LIMIT
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        return await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL,
        )

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trade_datas: Dict[str, Any] = raw_message["params"]
        symbol = trade_datas[0]
        for trade_data in trade_datas[1]:
            trade_timestamp: int = trade_data["time"]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                symbol=symbol)
            message_content = {
                "trading_pair": trading_pair,
                "trade_type": (float(TradeType.SELL.value) if trade_data["type"] == "sell" else float(TradeType.BUY.value)),
                "trade_id": trade_data["id"],
                "update_id": trade_timestamp,
                "price": trade_data["price"],
                "amount": trade_data["amount"],
            }
            trade_message: Optional[OrderBookMessage] = OrderBookMessage(
                message_type=OrderBookMessageType.TRADE,
                content=message_content,
                timestamp=trade_timestamp)

            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        diff_data = raw_message["params"]
        timestamp: float = time.time()
        update_id: int = raw_message["id"]

        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=diff_data[2])

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": diff_data[1]["bids"],
            "asks": diff_data[1]["asks"],
        }
        diff_message: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.DIFF,
            order_book_message_content,
            timestamp)

        message_queue.put_nowait(diff_message)

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            trade_params = []
            depth_params = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                trade_params.append(f"{symbol.upper()}")
                depth_params.append([f"{symbol.upper()}", CONSTANTS.DEPTH_LISTEN_LIMIT, CONSTANTS.DEPTH_PRICE_INTERVAL])
            payload = {
                "method": "deals.subscribe",
                "params": trade_params,
                "id": 1
            }
            subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)

            payload = {
                "method": "depths.subscribe",
                "params": depth_params,
                "id": 2
            }
            subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)

            await ws.send(subscribe_trade_request)
            await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...",
                exc_info=True
            )
            raise

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            event_type = event_message.get("method")
            channel = (self._diff_messages_queue_key if event_type == CONSTANTS.DIFF_EVENT_TYPE
                       else self._trade_messages_queue_key)
        return channel

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WSS_URL, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws
