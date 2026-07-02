import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS, gemini_web_utils as web_utils
from hummingbot.connector.exchange.gemini.gemini_order_book import GeminiOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.gemini.gemini_exchange import GeminiExchange


class GeminiAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60
    _DYNAMIC_SUBSCRIBE_ID_START = 100

    _logger: Optional[HummingbotLogger] = None
    _next_subscribe_id: int = _DYNAMIC_SUBSCRIBE_ID_START

    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'GeminiExchange',
                 api_factory: WebAssistantsFactory):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.WS_EVENT_TRADE
        self._diff_messages_queue_key = CONSTANTS.WS_EVENT_DEPTH_UPDATE
        self._api_factory = api_factory

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves order book snapshot from Gemini REST API.
        Gemini returns: {"bids": [{"price": "...", "amount": "...", "timestamp": "..."}], "asks": [...]}
        We convert to the format expected by the order book: {"bids": [[price, amount], ...], "asks": [[price, amount], ...]}
        """
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.ORDER_BOOK_PATH_URL.format(symbol)),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDER_BOOK_PATH_URL,
        )

        # Convert Gemini format to standard format
        bids = [[entry["price"], entry["amount"]] for entry in data.get("bids", [])]
        asks = [[entry["price"], entry["amount"]] for entry in data.get("asks", [])]

        return {"bids": bids, "asks": asks}

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to trade and depth streams via the Gemini Fast API WebSocket.
        """
        try:
            trade_streams = []
            depth_streams = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                trade_streams.append(CONSTANTS.WS_TRADE_STREAM.format(symbol))
                depth_streams.append(CONSTANTS.WS_DEPTH_STREAM.format(symbol))

            # Subscribe to trade streams
            payload = {
                "id": str(self.TRADE_STREAM_ID),
                "method": CONSTANTS.WS_METHOD_SUBSCRIBE,
                "params": trade_streams
            }
            subscribe_trade_request: WSJSONRequest = WSJSONRequest(payload=payload)

            # Subscribe to depth streams
            payload = {
                "id": str(self.DIFF_STREAM_ID),
                "method": CONSTANTS.WS_METHOD_SUBSCRIBE,
                "params": depth_streams
            }
            subscribe_depth_request: WSJSONRequest = WSJSONRequest(payload=payload)

            await ws.send(subscribe_trade_request)
            await ws.send(subscribe_depth_request)

            self.logger().info("Subscribed to public order book and trade channels...")
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
        await ws.connect(ws_url=web_utils.wss_url(),
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = GeminiOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # Skip subscription acknowledgment messages
        if "result" in raw_message or ("id" in raw_message and "t" not in raw_message):
            return
        # Trade messages are identified by the "t" (trade ID) field, not by "e"
        if "t" in raw_message and "s" in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                symbol=raw_message["s"])
            trade_message = GeminiOrderBook.trade_message_from_exchange(
                raw_message, {"trading_pair": trading_pair})
            message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # Skip subscription acknowledgment messages
        if "result" in raw_message or "id" in raw_message and "e" not in raw_message:
            return
        if raw_message.get("e") == CONSTANTS.WS_EVENT_DEPTH_UPDATE:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                symbol=raw_message["s"])
            order_book_message: OrderBookMessage = GeminiOrderBook.diff_message_from_exchange(
                raw_message, time.time(), {"trading_pair": trading_pair})
            message_queue.put_nowait(order_book_message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            event_type = event_message.get("e")
            if event_type == CONSTANTS.WS_EVENT_DEPTH_UPDATE:
                channel = self._diff_messages_queue_key
            elif "t" in event_message:
                # Trade messages have a "t" (trade ID) field but no "e" field
                channel = self._trade_messages_queue_key
        return channel

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning(f"Cannot subscribe to {trading_pair}: WebSocket not connected")
            return False
        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            payload = {
                "id": str(self._get_next_subscribe_id()),
                "method": CONSTANTS.WS_METHOD_SUBSCRIBE,
                "params": [
                    CONSTANTS.WS_TRADE_STREAM.format(symbol),
                    CONSTANTS.WS_DEPTH_STREAM.format(symbol),
                ]
            }
            subscribe_request: WSJSONRequest = WSJSONRequest(payload=payload)
            await self._ws_assistant.send(subscribe_request)
            self.add_trading_pair(trading_pair)
            self.logger().info(f"Subscribed to {trading_pair} order book and trade channels")
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Unexpected error subscribing to {trading_pair} channels")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning(f"Cannot unsubscribe from {trading_pair}: WebSocket not connected")
            return False
        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            payload = {
                "id": str(self._get_next_subscribe_id()),
                "method": CONSTANTS.WS_METHOD_UNSUBSCRIBE,
                "params": [
                    CONSTANTS.WS_TRADE_STREAM.format(symbol),
                    CONSTANTS.WS_DEPTH_STREAM.format(symbol),
                ]
            }
            unsubscribe_request: WSJSONRequest = WSJSONRequest(payload=payload)
            await self._ws_assistant.send(unsubscribe_request)
            self.remove_trading_pair(trading_pair)
            self.logger().info(f"Unsubscribed from {trading_pair} order book and trade channels")
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Unexpected error unsubscribing from {trading_pair} channels")
            return False

    @classmethod
    def _get_next_subscribe_id(cls) -> int:
        current_id = cls._next_subscribe_id
        cls._next_subscribe_id += 1
        return current_id
