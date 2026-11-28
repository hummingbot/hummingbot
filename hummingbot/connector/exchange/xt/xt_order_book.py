import time
from typing import Any, Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class XtOrderBook(OrderBook):
    @classmethod
    def snapshot_message_from_exchange(
        cls,
        msg: Dict[str, Any],
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBookMessage:
        data = dict(msg.get("result", msg))
        if metadata:
            data.update(metadata)

        update_id = int(data["lastUpdateId"])
        message_timestamp = timestamp if timestamp is not None else time.time()
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": data["trading_pair"],
                "update_id": update_id,
                "bids": data.get("bids", []),
                "asks": data.get("asks", []),
            },
            message_timestamp,
        )

    @classmethod
    def diff_message_from_exchange(
        cls,
        msg: Dict[str, Any],
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBookMessage:
        data = dict(msg["data"])
        if metadata:
            data.update(metadata)

        update_id = int(data["i"])
        return OrderBookMessage(
            OrderBookMessageType.DIFF,
            {
                "trading_pair": data["trading_pair"],
                "first_update_id": int(data["fi"]),
                "update_id": update_id,
                "bids": data.get("b", []),
                "asks": data.get("a", []),
            },
            timestamp if timestamp is not None else time.time(),
        )

    @classmethod
    def trade_message_from_exchange(
        cls,
        msg: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OrderBookMessage:
        data = dict(msg["data"])
        if metadata:
            data.update(metadata)

        buyer_is_maker = data["b"]
        trade_type = TradeType.SELL if buyer_is_maker else TradeType.BUY
        trade_timestamp = float(data["t"]) * 1e-3
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": data["trading_pair"],
                "trade_type": float(trade_type.value),
                "trade_id": str(data["i"]),
                "update_id": int(data["t"]),
                "price": data["p"],
                "amount": data["q"],
            },
            trade_timestamp,
        )
