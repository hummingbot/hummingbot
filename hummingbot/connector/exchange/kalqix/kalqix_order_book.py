from typing import Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class KalqixOrderBook(OrderBook):
    """
    KalqiX's `GET /markets/{ticker}/order-book` returns a snapshot:

        {
          "BUY":  [{ "price": "<base>", "price_formatted": "<dec>",
                     "quantity": "<base>", "quantity_formatted": "<dec>" }, ...],
          "SELL": [{ ...same... }, ...]
        }

    No `lastUpdateId` or sequence number is exposed — the endpoint returns
    a full snapshot per call. We synthesize `update_id` from the polling
    timestamp so Hummingbot's deduplication still sees a monotonic value.

    Public trade tape (`/markets/{ticker}/trades`) returns:

        { "data": [{ "trade_id": "<uuid>", "price": "<base>",
                     "price_formatted": "<dec>", "quantity": "<base>",
                     "quantity_formatted": "<dec>", "timestamp": <ms>,
                     "maker_side": "BUY"|"SELL" }, ...], "total": ... }

    `maker_side` tells us which side the maker was; the taker (and thus
    the trade direction) is the opposite.
    """

    @classmethod
    def snapshot_message_from_exchange(
        cls,
        msg: Dict[str, any],
        timestamp: float,
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        """Convert a KalqiX orderbook snapshot to a Hummingbot SNAPSHOT
        message. `msg` must already carry `trading_pair` in
        Hummingbot's `BASE-QUOTE` form (set by the data source before
        forwarding).

        Both bid and ask entries are emitted as `[price, quantity]`
        pairs in **formatted (human-readable)** decimal form. The
        exchange class places orders using `Decimal` math; the OrderBook
        being in formatted units lets strategies reason about prices the
        way humans do."""
        if metadata:
            msg.update(metadata)
        bids = [[level["price_formatted"], level["quantity_formatted"]]
                for level in msg.get("BUY") or []]
        asks = [[level["price_formatted"], level["quantity_formatted"]]
                for level in msg.get("SELL") or []]
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": msg["trading_pair"],
                # No server-side sequence; ms-precision timestamp is
                # monotonic enough.
                "update_id": int(timestamp * 1e3),
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp,
        )

    @classmethod
    def diff_message_from_exchange(
        cls,
        msg: Dict[str, any],
        timestamp: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        """KalqiX exposes no diff stream today — diffs aren't produced.

        Kept on the class for interface parity with other connectors;
        callers will only ever feed the tracker SNAPSHOT messages from
        the polled data source."""
        raise NotImplementedError(
            "KalqiX does not expose an order-book diff stream; the "
            "tracker is fed snapshot messages only."
        )

    @classmethod
    def trade_message_from_exchange(
        cls,
        msg: Dict[str, any],
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        """Convert a KalqiX public-trade record to a Hummingbot TRADE
        message.

        `msg["maker_side"]` is `BUY` if the maker was a buyer (the trade
        was filled by a taker sell, so the trade direction is SELL); and
        vice versa.
        """
        if metadata:
            msg.update(metadata)
        # Trade `timestamp` is microseconds since epoch; Hummingbot's
        # OrderBookMessage timestamp is seconds.
        ts_us = int(msg["timestamp"])
        trade_direction = TradeType.SELL if msg.get("maker_side") == "BUY" else TradeType.BUY
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg["trading_pair"],
                "trade_type": float(trade_direction.value),
                "trade_id": msg["trade_id"],
                "update_id": ts_us,
                "price": msg["price_formatted"],
                "amount": msg["quantity_formatted"],
            },
            timestamp=ts_us * 1e-6,
        )
