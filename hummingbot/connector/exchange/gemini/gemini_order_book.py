import time
from typing import Any, Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class GeminiOrderBook(OrderBook):

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, Any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": int(timestamp * 1000),
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, Any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        ts = timestamp or time.time()
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["trading_pair"],
            "update_id": int(ts * 1000),
            "first_update_id": int(ts * 1000),
            "bids": msg.get("bids", []),
            "asks": msg.get("asks", []),
        }, timestamp=ts)

    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, Any],
                                    metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        trade = msg["trade"]
        ts = float(trade.get("timestamp", time.time()))
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg.get("trading_pair", ""),
            "trade_type": float(TradeType.BUY.value) if trade.get("type") == "buy" else float(TradeType.SELL.value),
            "trade_id": trade.get("tid", 0),
            "update_id": int(ts * 1000),
            "price": trade["price"],
            "amount": trade["quantity"],
        }, timestamp=ts)
