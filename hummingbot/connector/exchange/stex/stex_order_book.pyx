import logging
from typing import (
    Dict,
    Optional
)
from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)

_stob_logger = None

cdef class StexOrderBook(OrderBook):
    def logger(cls) -> HummingbotLogger:
        global _stob_logger
        if _stob_logger is None:
            _stob_logger = logging.getLogger(__name__)
        return _stob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        msg_ts = int(timestamp * 1e-3)
        bids_data = []
        asks_data = []
        for bid in msg["data"]["bid"]:
            data = [bid["price"],bid["amount"]]
            bids_data.append(data)
        for ask in msg["data"]["ask"]:
            data = [ask["price"],ask["amount"]]
            asks_data.append(data)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": msg_ts,
            "bids": bids_data,
            "asks": asks_data
        }, timestamp=timestamp * 1e-3)

    @classmethod
    def diff_message_from_exchange(cls,msg: Dict[str, any],timestamp: Optional[float] = None,metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        msg_ts = int(timestamp * 1e-3)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["trading_pair"],
            "update_id": msg_ts,
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=timestamp * 1e-3)

    @classmethod
    def trade_message_from_exchange(cls, msg, metadata: Optional[Dict] = None):
        if metadata:
            msg.update(metadata)
        msg_ts = int(msg["timestamp"] * 1e-3)
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["trading_pair"],
            "trade_type": float(TradeType.SELL.value) if msg["order_type"] == "SELL" else float(TradeType.BUY.value),
            "trade_id": msg['id'],
            "update_id": msg_ts,
            "price": msg["price"],
            "amount": msg["amount"]
        }, timestamp=msg_ts)

    @classmethod
    def from_snapshot(cls, msg: OrderBookMessage) -> "OrderBook":
        retval = StexOrderBook()
        retval.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        return retval
