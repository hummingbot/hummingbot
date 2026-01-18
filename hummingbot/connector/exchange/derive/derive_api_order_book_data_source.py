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
        self._snapshot_messages = {}
        self._api_factory = api_factory
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._snapshot_messages_queue_key = "order_book_snapshot"

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieve orderbook snapshot for a trading pair.
        Since we're already subscribed to orderbook updates via the main WebSocket in _subscribe_channels,
        we simply wait for a snapshot message from the message queue.
        """
        # Check if we already have a cached snapshot
        if trading_pair in self._snapshot_messages:
            cached_snapshot = self._snapshot_messages[trading_pair]
            # Convert OrderBookMessage back to dict format for compatibility
            return {
                "params": {
                    "data": {
                        "instrument_name": await self._connector.exchange_symbol_associated_to_pair(trading_pair),
                        "publish_id": cached_snapshot.update_id,
                        "bids": cached_snapshot.bids,
                        "asks": cached_snapshot.asks,
                        "timestamp": cached_snapshot.timestamp * 1000  # Convert back to milliseconds
                    }
                }
            }

        # If no cached snapshot, wait for one from the main WebSocket stream
        # The main WebSocket connection in listen_for_subscriptions() is already
        # subscribed to orderbook updates, so we just need to wait
        message_queue = self._message_queue[self._snapshot_messages_queue_key]

        max_attempts = 100
        for _ in range(max_attempts):
            try:
                # Wait for snapshot message with timeout
                snapshot_event = await asyncio.wait_for(message_queue.get(), timeout=1.0)

                # Check if this snapshot is for our trading pair
                if "params" in snapshot_event and "data" in snapshot_event["params"]:
                    instrument_name = snapshot_event["params"]["data"].get("instrument_name")
                    ex_trading_pair = await self._connector.exchange_symbol_associated_to_pair(trading_pair)

                    if instrument_name == ex_trading_pair:
                        return snapshot_event
                    else:
                        # Put it back for other trading pairs
                        message_queue.put_nowait(snapshot_event)

            except asyncio.TimeoutError:
                continue

        raise RuntimeError(f"Failed to receive orderbook snapshot for {trading_pair} after {max_attempts} attempts. "
                           f"Make sure the main WebSocket connection is active.")

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
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_response.update({"trading_pair": trading_pair})
        data = snapshot_response["params"]["data"]
        snapshot_msg: OrderBookMessage = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": int(data['publish_id']),
            "bids": [[i[0], i[1]] for i in data.get('bids', [])],
            "asks": [[i[0], i[1]] for i in data.get('asks', [])],
        }, timestamp=snapshot_timestamp)
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
        self._snapshot_messages[trading_pair] = trade_message
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
