import asyncio
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from urllib.parse import urlparse

import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_derivative import KalshiPerpetualDerivative


class KalshiPerpetualAPIOrderBookDataSource(PerpetualAPIOrderBookDataSource):
    """
    Kalshi quotes margin markets per contract. Everything published to Hummingbot is converted to underlying units
    with the connector's contract size (price / contract_size, contracts * contract_size), so BTC-USD is in USD/BTC.

    Kalshi order book deltas carry the *change* at a price level, while Hummingbot diffs carry the new size, so a copy
    of each book is kept and updated in the websocket read loop, the only place where snapshots and deltas arrive in
    order. The same loop numbers every order book message with an id that never decreases, including across
    reconnections and REST snapshots, because the tracker drops diffs older than the last snapshot.
    """

    def __init__(
            self,
            trading_pairs: List[str],
            connector: 'KalshiPerpetualDerivative',
            api_factory: WebAssistantsFactory,
            domain: str = CONSTANTS.DEFAULT_DOMAIN
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._trade_messages_queue_key = CONSTANTS.WS_TRADE_MESSAGE
        self._diff_messages_queue_key = CONSTANTS.WS_ORDER_BOOK_DELTA_MESSAGE
        self._snapshot_messages_queue_key = CONSTANTS.WS_ORDER_BOOK_SNAPSHOT_MESSAGE
        self._funding_info_messages_queue_key = CONSTANTS.WS_TICKER_MESSAGE
        self._last_request_id = 0
        self._last_update_id = 0
        # Per connection: channel -> subscription id, order book subscription id -> last seq, and the local books
        # (market ticker -> side -> price -> contracts).
        self._channel_sids: Dict[str, int] = {}
        self._last_order_book_seq: Dict[int, int] = {}
        self._local_books: Dict[str, Dict[str, Dict[Decimal, Decimal]]] = {}

    async def get_last_traded_prices(self,
                                     trading_pairs: List[str],
                                     domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        market_response, funding_estimate = await asyncio.gather(
            self._connector._api_get(
                path_url=CONSTANTS.MARKET_PATH_URL.format(ticker=symbol),
                limit_id=CONSTANTS.MARKET_PATH_URL),
            self._connector._api_get(
                path_url=CONSTANTS.FUNDING_RATE_ESTIMATE_PATH_URL,
                params={"ticker": symbol},
                limit_id=CONSTANTS.FUNDING_RATE_ESTIMATE_PATH_URL),
        )
        contract_size = self._connector.get_contract_size(trading_pair)
        return FundingInfo(
            trading_pair=trading_pair,
            index_price=Decimal(market_response["market"]["reference_price"]["price"]) / contract_size,
            mark_price=Decimal(funding_estimate["mark_price"]) / contract_size,
            next_funding_utc_timestamp=int(datetime.fromisoformat(funding_estimate["next_funding_time"]).timestamp()),
            rate=Decimal(str(funding_estimate["funding_rate"])),
        )

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        return await self._connector._api_get(
            path_url=CONSTANTS.ORDER_BOOK_PATH_URL.format(ticker=symbol),
            limit_id=CONSTANTS.ORDER_BOOK_PATH_URL)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        order_book = snapshot_response["orderbook"]
        contract_size = self._connector.get_contract_size(trading_pair)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": self._next_update_id(),
            "bids": self._to_underlying_levels(order_book.get("bids") or [], contract_size),
            "asks": self._to_underlying_levels(order_book.get("asks") or [], contract_size),
        }, timestamp=self._time())

    async def _connected_websocket_assistant(self) -> WSAssistant:
        if self._api_factory.auth is None:
            raise ValueError("Kalshi requires API credentials to stream market data: its websocket handshake is signed.")
        url = web_utils.wss_url(self._domain)
        headers = self._api_factory.auth.header_for_authentication(method="GET", path=urlparse(url).path)
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.HEARTBEAT_TIME_INTERVAL, ws_headers=headers)
        return ws

    async def _subscribe_channels(self, ws: WSAssistant):
        try:
            # A new connection starts new subscriptions: sids, seq numbers and books restart from scratch.
            self._channel_sids.clear()
            self._last_order_book_seq.clear()
            self._local_books.clear()
            symbols = [
                await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                for trading_pair in self._trading_pairs
            ]
            payload = {
                "id": self._next_request_id(),
                "cmd": "subscribe",
                "params": {
                    "channels": [
                        CONSTANTS.WS_ORDER_BOOK_CHANNEL, CONSTANTS.WS_TRADE_CHANNEL, CONSTANTS.WS_TICKER_CHANNEL,
                    ],
                    "market_tickers": symbols,
                },
            }
            await ws.send(WSJSONRequest(payload=payload))
            self.logger().info("Subscribed to public order book, trade and ticker channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Unexpected error occurred subscribing to order book streams...")
            raise

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant):
        async for ws_response in websocket_assistant.iter_messages():
            data: Dict[str, Any] = ws_response.data
            if data is None:  # data will be None when the websocket is disconnected
                continue
            if data.get("type") in (CONSTANTS.WS_ORDER_BOOK_SNAPSHOT_MESSAGE, CONSTANTS.WS_ORDER_BOOK_DELTA_MESSAGE):
                self._check_order_book_sequence(data)
                self._apply_to_local_book(data)
            channel: str = self._channel_originating_message(event_message=data)
            if channel in self._get_messages_queue_keys():
                self._message_queue[channel].put_nowait(data)
            else:
                await self._process_message_for_unknown_channel(
                    event_message=data, websocket_assistant=websocket_assistant
                )

    def _check_order_book_sequence(self, message: Dict[str, Any]):
        sid, seq = message["sid"], message["seq"]
        last_seq = self._last_order_book_seq.get(sid)
        if last_seq is not None and seq != last_seq + 1:
            # Raising ConnectionError makes listen_for_subscriptions reconnect, which brings fresh snapshots.
            raise ConnectionError(
                f"Order book sequence gap on subscription {sid} (expected seq {last_seq + 1}, got {seq})"
            )
        self._last_order_book_seq[sid] = seq

    def _apply_to_local_book(self, message: Dict[str, Any]):
        msg = message["msg"]
        if message["type"] == CONSTANTS.WS_ORDER_BOOK_SNAPSHOT_MESSAGE:
            self._local_books[msg["market_ticker"]] = {
                side: {Decimal(price): Decimal(count) for price, count in msg.get(side) or []}
                for side in ("bid", "ask")
            }
        else:
            levels = self._local_books.setdefault(msg["market_ticker"], {"bid": {}, "ask": {}})[msg["side"]]
            price = Decimal(msg["price"])
            size = levels.get(price, Decimal("0")) + Decimal(msg["delta"])
            if size > 0:
                levels[price] = size
            else:
                levels.pop(price, None)
                size = Decimal("0")
            message["size"] = size
        message["update_id"] = self._next_update_id()

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        # Queue keys are Kalshi's message types; "subscribed" and "error" fall through to the unknown-channel handler.
        return event_message.get("type", "")

    async def _process_message_for_unknown_channel(
            self, event_message: Dict[str, Any], websocket_assistant: WSAssistant
    ):
        message_type = event_message.get("type")
        if message_type == CONSTANTS.WS_SUBSCRIBED_MESSAGE:
            self._channel_sids[event_message["msg"]["channel"]] = event_message["msg"]["sid"]
        elif message_type == CONSTANTS.WS_ERROR_MESSAGE:
            # Kalshi answers a rejected subscribe or update_subscription with an error and keeps the connection open,
            # without those streams. Raising reconnects after a pause, and the new subscription covers every tracked
            # pair. Not a ConnectionError, which would reconnect without pausing.
            raise IOError(f"Kalshi order book stream error: {event_message.get('msg')}")

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        msg = raw_message["msg"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(msg["market_ticker"])
        contract_size = self._connector.get_contract_size(trading_pair)
        snapshot_message = OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": trading_pair,
            "update_id": raw_message["update_id"],
            "bids": self._to_underlying_levels(msg.get("bid") or [], contract_size),
            "asks": self._to_underlying_levels(msg.get("ask") or [], contract_size),
        }, timestamp=self._time())
        message_queue.put_nowait(snapshot_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        msg = raw_message["msg"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(msg["market_ticker"])
        contract_size = self._connector.get_contract_size(trading_pair)
        level = [[Decimal(msg["price"]) / contract_size, raw_message["size"] * contract_size]]
        diff_message = OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": trading_pair,
            "update_id": raw_message["update_id"],
            "bids": level if msg["side"] == "bid" else [],
            "asks": level if msg["side"] == "ask" else [],
        }, timestamp=msg["ts_ms"] * 1e-3)
        message_queue.put_nowait(diff_message)

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        msg = raw_message["msg"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(msg["market_ticker"])
        contract_size = self._connector.get_contract_size(trading_pair)
        trade_message = OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": trading_pair,
            "trade_type": float(TradeType.BUY.value) if msg["taker_side"] == "bid" else float(TradeType.SELL.value),
            "trade_id": msg["trade_id"],
            "update_id": msg["ts_ms"],
            "price": Decimal(msg["price"]) / contract_size,
            "amount": Decimal(msg["count"]) * contract_size,
        }, timestamp=msg["ts_ms"] * 1e-3)
        message_queue.put_nowait(trade_message)

    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        msg = raw_message["msg"]
        trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(msg["market_ticker"])
        if trading_pair not in self._trading_pairs:
            return
        # Every funding-related field of the ticker message is optional.
        reference_price = msg.get("reference_price")
        mark_price = msg.get("settlement_mark_price")
        funding_rate = msg.get("funding_rate")
        if reference_price is None and mark_price is None and funding_rate is None:
            return
        contract_size = self._connector.get_contract_size(trading_pair)
        funding_info = FundingInfoUpdate(
            trading_pair=trading_pair,
            index_price=Decimal(reference_price["price"]) / contract_size if reference_price else None,
            mark_price=Decimal(mark_price["price"]) / contract_size if mark_price else None,
            next_funding_utc_timestamp=int(funding_rate["next_funding_time_ms"] * 1e-3) if funding_rate else None,
            rate=Decimal(str(funding_rate["rate"])) if funding_rate else None,
        )
        message_queue.put_nowait(funding_info)

    async def subscribe_to_trading_pair(self, trading_pair: str) -> bool:
        return await self._update_subscribed_markets(trading_pair=trading_pair, action="add_markets")

    async def unsubscribe_from_trading_pair(self, trading_pair: str) -> bool:
        return await self._update_subscribed_markets(trading_pair=trading_pair, action="delete_markets")

    async def _update_subscribed_markets(self, trading_pair: str, action: str) -> bool:
        """
        Adds or removes one market on the existing subscriptions (one sid per channel) with `update_subscription`.
        """
        verb = "subscribe to" if action == "add_markets" else "unsubscribe from"
        if self._ws_assistant is None or not self._channel_sids:
            self.logger().warning(f"Cannot {verb} {trading_pair}: WebSocket not connected")
            return False
        try:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            payload = {
                "id": self._next_request_id(),
                "cmd": "update_subscription",
                "params": {"sids": sorted(self._channel_sids.values()), "market_tickers": [symbol], "action": action},
            }
            await self._ws_assistant.send(WSJSONRequest(payload=payload))
            if action == "add_markets":
                self.add_trading_pair(trading_pair)
            else:
                self.remove_trading_pair(trading_pair)
                self._local_books.pop(symbol, None)
            self.logger().info(f"Requested to {verb} {trading_pair} order book, trade and ticker channels")
            return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error trying to {verb} {trading_pair}")
            return False

    @staticmethod
    def _to_underlying_levels(levels: List[List[str]], contract_size: Decimal) -> List[List[Decimal]]:
        return [[Decimal(price) / contract_size, Decimal(count) * contract_size] for price, count in levels]

    def _next_update_id(self) -> int:
        self._last_update_id += 1
        return self._last_update_id

    def _next_request_id(self) -> int:
        self._last_request_id += 1
        return self._last_request_id
