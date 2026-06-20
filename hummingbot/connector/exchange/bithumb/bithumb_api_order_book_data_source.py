import asyncio
import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.bithumb import bithumb_constants as CONSTANTS, bithumb_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.bithumb.bithumb_exchange import BithumbExchange


class BithumbAPIOrderBookDataSource(OrderBookTrackerDataSource):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "BithumbExchange",
        api_factory: WebAssistantsFactory,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory

    async def get_last_traded_prices(
        self, trading_pairs: List[str], domain: Optional[str] = None
    ) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        # symbol is like "BTC_KRW" → split to order_currency and payment_currency
        parts = symbol.split("_")
        order_currency = parts[0]
        payment_currency = parts[1] if len(parts) > 1 else CONSTANTS.DEFAULT_PAYMENT_CURRENCY

        path = CONSTANTS.ORDERBOOK_PATH_URL.format(
            order_currency=order_currency,
            payment_currency=payment_currency,
        )
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path),
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDERBOOK_PATH_URL,
        )

        data = response.get("data", {})
        timestamp = int(data.get("timestamp", 0)) * 1e-3

        bids = [
            (float(level["price"]), float(level["quantity"]))
            for level in data.get("bids", [])
        ]
        asks = [
            (float(level["price"]), float(level["quantity"]))
            for level in data.get("asks", [])
        ]

        content = {
            "trading_pair": trading_pair,
            "update_id": int(data.get("timestamp", 0)),
            "bids": bids,
            "asks": asks,
        }
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        content_list = raw_message.get("content", {}).get("list", [])
        for item in content_list:
            symbol = item.get("symbol", "")
            try:
                trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
            except Exception:
                continue

            # buySellGb: "1" = sell, "2" = buy
            buy_sell_gb = item.get("buySellGb", "1")
            trade_type = TradeType.BUY if buy_sell_gb == "2" else TradeType.SELL

            # contDtm: "2023-01-01 00:00:00.000000" - parse to timestamp
            cont_dtm = item.get("contDtm", "")
            try:
                from datetime import datetime
                ts = datetime.strptime(cont_dtm, "%Y-%m-%d %H:%M:%S.%f").timestamp()
            except Exception:
                ts = self._time()

            content = {
                "trade_id": f"{symbol}_{cont_dtm}",
                "trading_pair": trading_pair,
                "trade_type": float(trade_type.value),
                "amount": float(item.get("contQty", 0)),
                "price": float(item.get("contPrice", 0)),
            }
            message = OrderBookMessage(OrderBookMessageType.TRADE, content, ts)
            message_queue.put_nowait(message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # Bithumb sends full snapshots; treat as SNAPSHOT
        content_list = raw_message.get("content", {}).get("list", [])
        if not content_list:
            return

        symbol = content_list[0].get("symbol", "")
        try:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=symbol)
        except Exception:
            return

        datetime_str = raw_message.get("content", {}).get("datetime", "0")
        try:
            update_id = int(datetime_str)
            timestamp = update_id * 1e-3
        except (ValueError, TypeError):
            update_id = 0
            timestamp = self._time()

        bids = [
            (float(item["price"]), float(item["quantity"]))
            for item in content_list
            if item.get("orderType") == "bid"
        ]
        asks = [
            (float(item["price"]), float(item["quantity"]))
            for item in content_list
            if item.get("orderType") == "ask"
        ]

        content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "first_update_id": update_id,
            "bids": bids,
            "asks": asks,
        }
        message = OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp)
        message_queue.put_nowait(message)

    async def _subscribe_channels(self, ws: WSAssistant):
        symbols = [
            await self._connector.exchange_symbol_associated_to_pair(trading_pair=pair)
            for pair in self._trading_pairs
        ]
        # Subscribe to order book snapshots
        await ws.send(WSJSONRequest(payload={
            "type": CONSTANTS.WS_ORDERBOOK_EVENT_TYPE,
            "symbols": symbols,
        }))
        # Subscribe to trades
        await ws.send(WSJSONRequest(payload={
            "type": CONSTANTS.WS_TRADE_EVENT_TYPE,
            "symbols": symbols,
        }))
        self.logger().info("Subscribed to Bithumb public order book and trade streams.")

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            raw = ws_response.data
            if isinstance(raw, bytes):
                raw = raw.decode()
            try:
                message = json.loads(raw)
            except Exception:
                self.logger().warning("Received non-JSON Bithumb WebSocket payload: %s", raw)
                continue

            msg_type = message.get("type")
            if msg_type == CONSTANTS.WS_TRADE_EVENT_TYPE:
                self._message_queue[self._trade_messages_queue_key].put_nowait(message)
            elif msg_type == CONSTANTS.WS_ORDERBOOK_EVENT_TYPE:
                self._message_queue[self._diff_messages_queue_key].put_nowait(message)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        return event_message.get("type", "")

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.WS_URL, ping_timeout=CONSTANTS.PING_INTERVAL)
        return ws
