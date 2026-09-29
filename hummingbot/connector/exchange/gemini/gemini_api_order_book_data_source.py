import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

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
        self._snapshot_symbols: Set[str] = set()
        self._last_update_ids: Dict[str, int] = {}
        self._subscription_ack_futures: Dict[str, asyncio.Future] = {}
        self._dynamic_snapshot_futures: Dict[str, asyncio.Future] = {}
        self._pending_dynamic_snapshots: Dict[str, Dict[str, Any]] = {}

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
            params={"limit_bids": 0, "limit_asks": 0},
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
                self._snapshot_symbols.discard(symbol.lower())
                self._last_update_ids.pop(symbol.lower(), None)
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
        # snapshot=-1 makes the first depthUpdate for each subscribed symbol a
        # complete sequence-bearing book with U == u.
        await ws.connect(ws_url=web_utils.wss_url(snapshot=-1),
                         ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_timestamp: float = time.time()
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        pending_snapshot = self._pending_dynamic_snapshots.pop(symbol.lower(), None)
        if pending_snapshot is not None:
            snapshot_msg = await self._snapshot_message_from_depth_update(pending_snapshot, snapshot_timestamp)
        else:
            snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
            snapshot_msg: OrderBookMessage = GeminiOrderBook.snapshot_message_from_exchange(
                snapshot,
                snapshot_timestamp,
                metadata={"trading_pair": trading_pair}
            )
        return snapshot_msg

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        # Gemini websocket snapshots are the only snapshots with an update ID
        # comparable to differential U/u values. Gap detection below reconnects
        # and obtains a fresh one, so do not overwrite it with hourly REST books.
        message_queue = self._message_queue[self._snapshot_messages_queue_key]
        while True:
            try:
                snapshot_event = await message_queue.get()
                await self._parse_order_book_snapshot_message(
                    raw_message=snapshot_event,
                    message_queue=output,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing Gemini order book snapshots")
                await self._sleep(1.0)

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

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        snapshot_message = await self._snapshot_message_from_depth_update(raw_message)
        message_queue.put_nowait(snapshot_message)

    async def _snapshot_message_from_depth_update(
            self,
            raw_message: Dict[str, Any],
            timestamp: Optional[float] = None) -> OrderBookMessage:
        symbol = raw_message["s"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
        timestamp = timestamp or CONSTANTS.convert_timestamp_to_seconds(raw_message.get("E", 0)) or time.time()
        snapshot = {
            "lastUpdateId": int(raw_message["u"]),
            "bids": raw_message.get("b", []),
            "asks": raw_message.get("a", []),
        }
        return GeminiOrderBook.snapshot_message_from_exchange(
            snapshot,
            timestamp,
            {"trading_pair": trading_pair},
        )

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if self._resolve_subscription_ack(event_message):
            return channel
        if "result" not in event_message:
            event_type = event_message.get("e")
            if event_type == CONSTANTS.WS_EVENT_DEPTH_UPDATE:
                symbol = str(event_message.get("s", "")).lower()
                first_update_id = int(event_message.get("U", 0))
                last_update_id = int(event_message.get("u", 0))
                if symbol not in self._snapshot_symbols:
                    self._snapshot_symbols.add(symbol)
                    self._last_update_ids[symbol] = last_update_id
                    snapshot_future = self._dynamic_snapshot_futures.get(symbol)
                    if snapshot_future is not None:
                        self._pending_dynamic_snapshots[symbol] = dict(event_message)
                        if not snapshot_future.done():
                            snapshot_future.set_result(dict(event_message))
                    else:
                        channel = self._snapshot_messages_queue_key
                else:
                    previous_update_id = self._last_update_ids[symbol]
                    if last_update_id <= previous_update_id:
                        return ""
                    if first_update_id > previous_update_id + 1:
                        self._snapshot_symbols.discard(symbol)
                        self._last_update_ids.pop(symbol, None)
                        raise ConnectionError(
                            f"Gemini order book sequence gap for {symbol}: "
                            f"expected {previous_update_id + 1}, received {first_update_id}.")
                    self._last_update_ids[symbol] = last_update_id
                    channel = self._diff_messages_queue_key
            elif "t" in event_message:
                # Trade messages have a "t" (trade ID) field but no "e" field
                channel = self._trade_messages_queue_key
        return channel

    def _resolve_subscription_ack(self, event_message: Dict[str, Any]) -> bool:
        request_id = event_message.get("id")
        if request_id is None or not any(key in event_message for key in ("result", "status", "error")):
            return False
        future = self._subscription_ack_futures.get(str(request_id))
        if future is not None and not future.done():
            future.set_result(dict(event_message))
        return True

    @staticmethod
    def _is_successful_subscription_ack(ack: Dict[str, Any]) -> bool:
        status = ack.get("status")
        return status in (None, 200) and "error" not in ack

    async def _send_subscription_request_and_wait_for_ack(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        request_id = str(payload["id"])
        future = asyncio.get_event_loop().create_future()
        self._subscription_ack_futures[request_id] = future
        try:
            await self._ws_assistant.send(WSJSONRequest(payload=payload))
            return await asyncio.wait_for(future, timeout=CONSTANTS.WS_SUBSCRIPTION_REQUEST_TIMEOUT)
        finally:
            self._subscription_ack_futures.pop(request_id, None)

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning(f"Cannot subscribe to {trading_pair}: WebSocket not connected")
            return False
        subscribed = False
        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            self._snapshot_symbols.discard(symbol.lower())
            self._last_update_ids.pop(symbol.lower(), None)
            self._pending_dynamic_snapshots.pop(symbol.lower(), None)
            snapshot_future = asyncio.get_event_loop().create_future()
            self._dynamic_snapshot_futures[symbol.lower()] = snapshot_future
            payload = {
                "id": str(self._get_next_subscribe_id()),
                "method": CONSTANTS.WS_METHOD_SUBSCRIBE,
                "params": [
                    CONSTANTS.WS_TRADE_STREAM.format(symbol),
                    CONSTANTS.WS_DEPTH_STREAM.format(symbol),
                ]
            }
            ack = await self._send_subscription_request_and_wait_for_ack(payload)
            if not self._is_successful_subscription_ack(ack or {}):
                self.logger().warning(f"Subscription to {trading_pair} failed: {ack}")
                return False
            await asyncio.wait_for(snapshot_future, timeout=CONSTANTS.WS_DYNAMIC_SNAPSHOT_TIMEOUT)
            self.add_trading_pair(trading_pair)
            subscribed = True
            self.logger().info(f"Subscribed to {trading_pair} order book and trade channels")
            return True
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            self.logger().warning(f"Timed out subscribing to {trading_pair} channels")
            return False
        except Exception:
            self.logger().exception(f"Unexpected error subscribing to {trading_pair} channels")
            return False
        finally:
            if "symbol" in locals():
                self._dynamic_snapshot_futures.pop(symbol.lower(), None)
                if not subscribed:
                    self._snapshot_symbols.discard(symbol.lower())
                    self._last_update_ids.pop(symbol.lower(), None)
                    self._pending_dynamic_snapshots.pop(symbol.lower(), None)

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
            ack = await self._send_subscription_request_and_wait_for_ack(payload)
            if not self._is_successful_subscription_ack(ack or {}):
                self.logger().warning(f"Unsubscription from {trading_pair} failed: {ack}")
                return False
            self.remove_trading_pair(trading_pair)
            self._snapshot_symbols.discard(symbol.lower())
            self._last_update_ids.pop(symbol.lower(), None)
            self._pending_dynamic_snapshots.pop(symbol.lower(), None)
            self.logger().info(f"Unsubscribed from {trading_pair} order book and trade channels")
            return True
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            self.logger().warning(f"Timed out unsubscribing from {trading_pair} channels")
            return False
        except Exception:
            self.logger().exception(f"Unexpected error unsubscribing from {trading_pair} channels")
            return False

    @classmethod
    def _get_next_subscribe_id(cls) -> int:
        current_id = cls._next_subscribe_id
        cls._next_subscribe_id += 1
        return current_id

    async def _on_order_stream_interruption(self, websocket_assistant: Optional[WSAssistant] = None):
        self._snapshot_symbols.clear()
        self._last_update_ids.clear()
        await super()._on_order_stream_interruption(websocket_assistant=websocket_assistant)
