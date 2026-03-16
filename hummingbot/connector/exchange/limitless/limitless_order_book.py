from typing import Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class LimitlessOrderBook(OrderBook):

    @classmethod
    def snapshot_message_from_exchange(
        cls,
        msg: Dict[str, any],
        timestamp: float,
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": msg["trading_pair"],
                "update_id": int(timestamp * 1e3),
                "bids": msg.get("bids", []),
                "asks": msg.get("asks", []),
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
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.DIFF,
            {
                "trading_pair": msg["trading_pair"],
                "update_id": int((timestamp or 0) * 1e3),
                "bids": msg.get("bids", []),
                "asks": msg.get("asks", []),
            },
            timestamp=timestamp,
        )

    @classmethod
    def trade_message_from_exchange(
        cls,
        msg: Dict[str, any],
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        ts = msg.get("time", 0)
        if ts > 1e12:
            ts = ts * 1e-3
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg["trading_pair"],
                "trade_type": float(TradeType.SELL.value) if msg.get("side") == "SELL" else float(TradeType.BUY.value),
                "trade_id": msg.get("trade_id", str(int(ts * 1e6))),
                "price": float(msg.get("price", 0)),
                "amount": float(msg.get("amount", 0)),
            },
            timestamp=ts,
        )
