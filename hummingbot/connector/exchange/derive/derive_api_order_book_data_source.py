import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# from bidict import bidict
from hummingbot.connector.exchange.derive import derive_constants as CONSTANTS, derive_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.derive.derive_exchange import DeriveExchange


class DeriveAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'DeriveExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._domain = domain
        self._api_factory = api_factory
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._snapshot_messages_queue_key = "order_book_snapshot"

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        pass

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            trade_params = []
            order_book_params = []
            for trading_pair in self._trading_pairs:
                trade_params.append(f"trades.{trading_pair.upper()}")
                order_book_params.append(f"orderbook.{trading_pair.upper()}.1.100")

            trades_payload = {
                "method": "subscribe",
                "params": {
                    "channels": trade_params
                }
            }
            subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=trades_payload)
            order_book_payload = {
                "method": "subscribe",
                "params": {
                    "channels": order_book_params
                }

            }
            subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=order_book_payload)

            await ws.send(subscribe_trade_request)
            await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to public order book, trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error occurred subscribing to order book data streams.")
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        url = f"{web_utils.wss_url(self._domain)}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_timestamp: float = self._time()
        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": snapshot_timestamp,
            "bids": [],
            "asks": [],
        }
        snapshot_msg: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            order_book_message_content,
            snapshot_timestamp)
        return snapshot_msg

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
            raw_message["params"]["data"]["instrument_name"])
        data = raw_message["params"]["data"]
        timestamp: float = raw_message["params"]["data"]["timestamp"] * 1e-3
        trade_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": int(data['publish_id']),
            "bids": [[float(i[0]), float(i[1])] for i in data['bids']],
            "asks": [[float(i[0]), float(i[1])] for i in data['asks']],
        }, timestamp=timestamp)
        message_queue.put_nowait(trade_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message["params"]["data"]
        for trade_data in data:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                trade_data["instrument_name"])
            trade_message: OrderBookMessage = OrderBookMessage(OrderBookMessageType.TRADE, {
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.SELL.value) if trade_data["direction"] == "sell" else float(
                    TradeType.BUY.value),
                "trade_id": trade_data["trade_id"],
                "price": float(trade_data["trade_price"]),
                "amount": float(trade_data["trade_amount"])
            }, timestamp=trade_data["timestamp"] * 1e-3)
            message_queue.put_nowait(trade_message)

    async def listen_for_order_book_diffs(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "error" not in event_message:
            if "params" in event_message:
                stream_name = event_message["params"]["channel"]
                if "orderbook" in stream_name:
                    channel = self._snapshot_messages_queue_key
                elif "trades" in stream_name:
                    channel = self._trade_messages_queue_key
            return channel
