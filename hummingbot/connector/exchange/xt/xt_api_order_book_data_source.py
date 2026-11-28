import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from hummingbot.connector.exchange.xt import xt_constants as CONSTANTS, xt_web_utils as web_utils
from hummingbot.connector.exchange.xt.xt_order_book import XtOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest, WSPlainTextRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.xt.xt_exchange import XtExchange


class XtAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "XtExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._domain = domain
        self._api_factory = api_factory
        self._diff_messages_queue_key = CONSTANTS.WS_PUBLIC_DEPTH_TOPIC
        self._trade_messages_queue_key = CONSTANTS.WS_PUBLIC_TRADE_TOPIC
        self._symbol_associated_to_trading_pair: Dict[str, str] = {}
        self._next_request_id = 1
        self._last_diff_update_ids: Dict[str, int] = {}

    async def get_last_traded_prices(
        self,
        trading_pairs: List[str],
        domain: Optional[str] = None,
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        self._symbol_associated_to_trading_pair[symbol] = trading_pair

        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.DEPTH_PATH_URL, domain=self._domain),
            params={"symbol": symbol, "limit": 500},
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.PUBLIC_ORDER_BOOK_LIMIT_ID,
        )
        web_utils.result_from_response(response, "order book snapshot")
        return response

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._request_order_book_snapshot(trading_pair)
        return XtOrderBook.snapshot_message_from_exchange(snapshot, metadata={"trading_pair": trading_pair})

    async def _request_order_book_snapshots(self, output: asyncio.Queue):
        # Periodic snapshots must pass the same freshness check and ordered
        # consumer as gap recovery; the native snapshot router cannot replay
        # changes supplied only by a newer recovery snapshot.
        await super()._request_order_book_snapshots(output=self._message_queue[self._diff_messages_queue_key])

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WSS_PUBLIC_URL,
            ping_timeout=CONSTANTS.WS_RESPONSE_TIMEOUT,
            message_timeout=CONSTANTS.WS_RESPONSE_TIMEOUT,
            ws_headers={"Sec-WebSocket-Extensions": "permessage-deflate"},
        )
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            self._last_diff_update_ids.clear()
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                self._symbol_associated_to_trading_pair[symbol] = trading_pair
                payload = {
                    "method": "subscribe",
                    "params": [
                        f"{CONSTANTS.WS_PUBLIC_TRADE_TOPIC}@{symbol}",
                        f"{CONSTANTS.WS_PUBLIC_DEPTH_TOPIC}@{symbol}",
                    ],
                    "id": self._new_request_id(),
                }
                request = WSJSONRequest(payload=payload)
                async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_SUBSCRIPTION_LIMIT_ID):
                    await ws.send(request)

            self.logger().info("Subscribed to XT public order book and trade channels.")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error subscribing to XT public streams.")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        while True:
            try:
                await asyncio.wait_for(
                    super()._process_websocket_messages(websocket_assistant),
                    timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
                )
                return
            except asyncio.TimeoutError:
                await websocket_assistant.send(WSPlainTextRequest(CONSTANTS.WS_PING_REQUEST))

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", {})
        symbol = data.get("s")
        trading_pair = self._symbol_associated_to_trading_pair.get(symbol)
        if trading_pair is None and symbol is not None:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
        if trading_pair is None:
            return
        message_queue.put_nowait(XtOrderBook.trade_message_from_exchange(raw_message, {"trading_pair": trading_pair}))

    async def _parse_order_book_diff_message(
        self, raw_message: Union[Dict[str, Any], OrderBookMessage], message_queue: asyncio.Queue
    ):
        if isinstance(raw_message, OrderBookMessage):
            trading_pair = raw_message.trading_pair
            last_update_id = self._last_diff_update_ids.get(trading_pair)
            if last_update_id is None or raw_message.update_id >= last_update_id:
                self._last_diff_update_ids[trading_pair] = raw_message.update_id
                message_queue.put_nowait(raw_message)
            return
        data = raw_message.get("data", {})
        symbol = data.get("s")
        trading_pair = self._symbol_associated_to_trading_pair.get(symbol)
        if trading_pair is None and symbol is not None:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
        if trading_pair is None:
            return
        message = XtOrderBook.diff_message_from_exchange(raw_message, metadata={"trading_pair": trading_pair})
        last_update_id = self._last_diff_update_ids.get(trading_pair)
        if last_update_id is not None and message.update_id <= last_update_id:
            return
        if last_update_id is None or message.first_update_id > last_update_id + 1:
            snapshot = await self._order_book_snapshot(trading_pair)
            if last_update_id is not None and snapshot.update_id < last_update_id:
                raise IOError(f"XT order book snapshot for {trading_pair} is older than the last update.")
            # Use the same output queue so the native tracker receives recovery before new diffs.
            message_queue.put_nowait(snapshot)
            last_update_id = snapshot.update_id
            self._last_diff_update_ids[trading_pair] = last_update_id
            if message.update_id <= last_update_id:
                return
            if message.first_update_id > last_update_id + 1:
                raise IOError(f"XT order book snapshot for {trading_pair} does not bridge the sequence gap.")
        self._last_diff_update_ids[trading_pair] = message.update_id
        message_queue.put_nowait(message)

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data", {})
        symbol = data.get("s")
        trading_pair = self._symbol_associated_to_trading_pair.get(symbol)
        if trading_pair is None and symbol is not None:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
        if trading_pair is None:
            return
        message = XtOrderBook.snapshot_message_from_exchange(
            {"result": {"lastUpdateId": data.get("i"), "bids": data.get("b", []), "asks": data.get("a", [])}},
            metadata={"trading_pair": trading_pair},
        )
        message_queue.put_nowait(message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        if event_message == CONSTANTS.WS_PONG_RESPONSE:
            return ""
        if not isinstance(event_message, dict):
            return ""
        topic = event_message.get("topic", "")
        if topic == CONSTANTS.WS_PUBLIC_DEPTH_TOPIC:
            return self._diff_messages_queue_key
        if topic == CONSTANTS.WS_PUBLIC_TRADE_TOPIC:
            return self._trade_messages_queue_key
        return ""

    async def _process_message_for_unknown_channel(self, event_message: Dict[str, Any], websocket_assistant: WSAssistant):
        if event_message == CONSTANTS.WS_PONG_RESPONSE:
            return
        if not isinstance(event_message, dict):
            self.logger().debug(f"Received XT public websocket message in unknown format: {event_message}")
            return
        code = event_message.get("code")
        if code == 0:
            self.logger().info(f"XT public websocket subscription acknowledged: {event_message}")
        elif code is not None:
            raise IOError(f"XT public websocket subscription failed: {event_message}")

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning("Cannot subscribe to XT pair: websocket is not connected.")
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            self._symbol_associated_to_trading_pair[symbol] = trading_pair
            payload = {
                "method": "subscribe",
                "params": [
                    f"{CONSTANTS.WS_PUBLIC_TRADE_TOPIC}@{symbol}",
                    f"{CONSTANTS.WS_PUBLIC_DEPTH_TOPIC}@{symbol}",
                ],
                "id": self._new_request_id(),
            }
            async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_SUBSCRIPTION_LIMIT_ID):
                await self._ws_assistant.send(WSJSONRequest(payload=payload))
            self.add_trading_pair(trading_pair)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Unexpected error subscribing to XT {trading_pair}.")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning("Cannot unsubscribe from XT pair: websocket is not connected.")
            return False

        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            payload = {
                "method": "unsubscribe",
                "params": [
                    f"{CONSTANTS.WS_PUBLIC_TRADE_TOPIC}@{symbol}",
                    f"{CONSTANTS.WS_PUBLIC_DEPTH_TOPIC}@{symbol}",
                ],
                "id": self._new_request_id(),
            }
            async with self._api_factory.throttler.execute_task(limit_id=CONSTANTS.WS_SUBSCRIPTION_LIMIT_ID):
                await self._ws_assistant.send(WSJSONRequest(payload=payload))
            self._symbol_associated_to_trading_pair.pop(symbol, None)
            self._last_diff_update_ids.pop(trading_pair, None)
            self.remove_trading_pair(trading_pair)
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Unexpected error unsubscribing from XT {trading_pair}.")
            return False

    def _new_request_id(self) -> str:
        request_id = str(self._next_request_id)
        self._next_request_id += 1
        return request_id
