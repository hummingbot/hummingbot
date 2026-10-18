import asyncio
import time
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import hummingbot.connector.derivative.true_perpetual.true_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.true_perpetual.true_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.derivative.true_perpetual.true_perpetual_derivative import TruePerpetualDerivative


class TruePerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    """
    Public market data over wss://app.truefinance.ai/api/ws/perps.

    Frames: {"topic": "orderbook:BTCUSDC", "type": "snapshot" | "delta", "ts", "data": {...}}
            {"topic": "trades:BTCUSDC",    "type": "delta",  "data": [{id, price, size, side, created_at}, ...]}
            {"topic": "mark:BTCUSDC",      "type": "update", "data": {"market", "mark_price"}}
    The server sends {"op": "ping"} and expects {"op": "pong"}; a missed pong closes the socket.
    The upgrade needs a short lived token from POST /ws-token, signed with the bot key.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            trading_pairs: List[str],
            connector: "TruePerpetualDerivative",
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trading_pairs: List[str] = trading_pairs
        self._message_queue: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._snapshot_messages_queue_key = "orderbook_snapshot"
        self._diff_messages_queue_key = "orderbook_delta"
        self._trade_messages_queue_key = "trades"
        self._funding_info_messages_queue_key = "mark"
        self._last_mark_prices: Dict[str, Decimal] = {}

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        market = await self._connector.market_info(symbol)
        mark_price = await self._request_mark_price(symbol)
        rate = Decimal(str(market.get("fundingRate8h") or "0"))
        return FundingInfo(
            trading_pair=trading_pair,
            index_price=mark_price,
            mark_price=mark_price,
            next_funding_utc_timestamp=self._next_funding_timestamp(),
            rate=rate,
        )

    @staticmethod
    def _next_funding_timestamp(now: Optional[float] = None) -> int:
        """Funding settles every 8 hours; the next boundary is the best estimate the public API gives."""
        now = now if now is not None else time.time()
        interval = CONSTANTS.FUNDING_INTERVAL_SECONDS
        return int((int(now) // interval + 1) * interval)

    async def _request_mark_price(self, symbol: str) -> Decimal:
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(CONSTANTS.MARK_PATH_URL, domain=self._domain),
            params={"market": symbol},
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.MARK_PATH_URL,
        )
        return Decimal(str(response["mark"]))

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        rest_assistant = await self._api_factory.get_rest_assistant()
        response = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(CONSTANTS.ORDERBOOK_PATH_URL, domain=self._domain),
            params={"market": symbol, "depth": 100},
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDERBOOK_PATH_URL,
        )
        return response.get("data", response)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot = await self._request_order_book_snapshot(trading_pair)
        timestamp = time.time()
        # Update ids are server milliseconds everywhere (REST snapshot, websocket snapshot and delta),
        # so a REST reset and the stream that follows it stay comparable for the order book tracker.
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": self._update_id(snapshot, timestamp),
            "bids": self._levels(snapshot.get("bids"), descending=True),
            "asks": self._levels(snapshot.get("asks")),
        }, timestamp=timestamp)

    @staticmethod
    def _update_id(data: Dict[str, Any], timestamp: float) -> int:
        """Server milliseconds of the message; the venue's own `ts` when present, the local clock otherwise."""
        ts = data.get("ts")
        return int(ts) if ts else int(timestamp * 1e3)

    @staticmethod
    def _levels(raw: Any, descending: bool = False) -> List[List[str]]:
        """The REST book is {price: size}; the websocket book is [[price, size], ...]. Both become [[price, size]]."""
        if raw is None:
            return []
        if isinstance(raw, dict):
            levels = [[str(price), str(size)] for price, size in raw.items()]
        else:
            levels = [[str(level[0]), str(level[1])] for level in raw]
        levels.sort(key=lambda level: Decimal(level[0]), reverse=descending)
        return levels

    async def _connected_websocket_assistant(self) -> WSAssistant:
        headers: Dict[str, str] = {}
        token = await self._connector.ws_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(
            ws_url=web_utils.wss_url(domain=self._domain),
            ws_headers=headers,
            ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL,
            message_timeout=CONSTANTS.SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE,
        )
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            args: List[str] = []
            for trading_pair in self._trading_pairs:
                args.extend(await self._topics_for(trading_pair))
            await ws.send(WSJSONRequest(payload={"op": "subscribe", "args": args}))
            self.logger().info("Subscribed to TRUE order book, trades and mark price channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to TRUE market data streams...")
            raise

    async def _topics_for(self, trading_pair: str) -> List[str]:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        return [
            f"{CONSTANTS.WS_ORDERBOOK_TOPIC}:{symbol}",
            f"{CONSTANTS.WS_TRADES_TOPIC}:{symbol}",
            f"{CONSTANTS.WS_MARK_TOPIC}:{symbol}",
        ]

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            self.logger().warning(f"Cannot subscribe to {trading_pair}: websocket not connected.")
            return False
        try:
            await self._ws_assistant.send(WSJSONRequest(payload={"op": "subscribe", "args": await self._topics_for(trading_pair)}))
            return True
        except Exception:
            self.logger().exception(f"Error subscribing to {trading_pair}")
            return False

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        if self._ws_assistant is None:
            return False
        try:
            await self._ws_assistant.send(WSJSONRequest(payload={"op": "unsubscribe", "args": await self._topics_for(trading_pair)}))
            return True
        except Exception:
            self.logger().exception(f"Error unsubscribing from {trading_pair}")
            return False

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        topic = str(event_message.get("topic") or "")
        kind = str(event_message.get("type") or "")
        if topic.startswith(f"{CONSTANTS.WS_ORDERBOOK_TOPIC}:"):
            return self._snapshot_messages_queue_key if kind == "snapshot" else self._diff_messages_queue_key
        if topic.startswith(f"{CONSTANTS.WS_TRADES_TOPIC}:"):
            return self._trade_messages_queue_key
        if topic.startswith(f"{CONSTANTS.WS_MARK_TOPIC}:"):
            return self._funding_info_messages_queue_key
        return ""

    async def _process_message_for_unknown_channel(self, event_message: Dict[str, Any], websocket_assistant: WSAssistant):
        op = event_message.get("op")
        if op == "ping":
            await websocket_assistant.send(WSJSONRequest(payload={"op": "pong"}))
        elif op == "subscribe" and event_message.get("failed"):
            self.logger().warning(f"TRUE websocket refused topics: {event_message.get('failed')}")
        elif op == "error":
            self.logger().warning(f"TRUE websocket error: {event_message}")

    @staticmethod
    def _symbol_of(topic: str) -> str:
        return topic.split(":", 1)[1] if ":" in topic else topic

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data") or {}
        symbol = data.get("market") or self._symbol_of(str(raw_message.get("topic", "")))
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
        timestamp = float(raw_message.get("ts") or time.time() * 1e3) / 1e3
        update_id = self._update_id(raw_message, timestamp)
        message_queue.put_nowait(OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": self._levels(data.get("bids"), descending=True),
            "asks": self._levels(data.get("asks")),
        }, timestamp=timestamp))

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data") or {}
        symbol = data.get("market") or self._symbol_of(str(raw_message.get("topic", "")))
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
        timestamp = float(raw_message.get("ts") or time.time() * 1e3) / 1e3
        update_id = self._update_id(raw_message, timestamp)
        message_queue.put_nowait(OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": self._levels(data.get("bids"), descending=True),
            "asks": self._levels(data.get("asks")),
        }, timestamp=timestamp))

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data")
        rows = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        for trade in rows:
            symbol = trade.get("market") or self._symbol_of(str(raw_message.get("topic", "")))
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
            created_at = float(trade.get("created_at") or raw_message.get("ts") or time.time() * 1e3) / 1e3
            side = str(trade.get("side") or "").upper()
            message_queue.put_nowait(OrderBookMessage(OrderBookMessageType.TRADE, {
                "trading_pair": trading_pair,
                "trade_type": float(TradeType.BUY.value) if side == "BUY" else float(TradeType.SELL.value),
                "trade_id": str(trade.get("id") or int(created_at * 1e3)),
                "price": str(trade.get("price")),
                "amount": str(trade.get("size")),
            }, timestamp=created_at))

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data = raw_message.get("data") or {}
        symbol = data.get("market") or self._symbol_of(str(raw_message.get("topic", "")))
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol)
        if trading_pair not in self._trading_pairs:
            return
        mark = data.get("mark_price")
        if mark is None:
            return
        mark_price = Decimal(str(mark))
        self._last_mark_prices[trading_pair] = mark_price
        # The 8h rate lives on the market list (cached for a minute by the connector), so every
        # mark update re-reads it and a rate change at the venue reaches the strategy within a minute.
        rate: Optional[Decimal] = None
        try:
            market = await self._connector.market_info(symbol)
            raw_rate = market.get("fundingRate8h")
            if raw_rate is not None:
                rate = Decimal(str(raw_rate))
        except Exception:
            self.logger().debug(f"Could not refresh the funding rate for {trading_pair}", exc_info=True)
        message_queue.put_nowait(FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=mark_price,
            mark_price=mark_price,
            next_funding_utc_timestamp=self._next_funding_timestamp(),
            rate=rate,
        ))
