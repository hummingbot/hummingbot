#!/usr/bin/env python
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

_krob_logger = None


cdef class KrakenOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _krob_logger
        if _krob_logger is None:
            _krob_logger = logging.getLogger(__name__)
        return _krob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"].replace("/", ""),
            "update_id": msg["latest_update"],
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=timestamp * 1e-3)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["trading_pair"].replace("/", ""),
            "update_id": msg["update_id"],
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=timestamp * 1e-3)

    @classmethod
    def snapshot_ws_message_from_exchange(cls,
                                          msg: Dict[str, any],
                                          timestamp: Optional[float] = None,
                                          metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"].replace("/", ""),
            "update_id": msg["update_id"],
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=timestamp * 1e-3)

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        if metadata:
            msg.update(metadata)
        ts = float(msg["trade"][2])
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["pair"].replace("/", ""),
            "trade_type": float(TradeType.SELL.value) if msg["trade"][3] == "s" else float(TradeType.BUY.value),
            "trade_id": ts,
            "update_id": ts,
            "price": msg["trade"][0],
            "amount": msg["trade"][1]
        }, timestamp=ts * 1e-3)

    @classmethod
    def from_snapshot(cls, msg: OrderBookMessage) -> "OrderBook":
        retval = KrakenOrderBook()
        retval.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        return retval
