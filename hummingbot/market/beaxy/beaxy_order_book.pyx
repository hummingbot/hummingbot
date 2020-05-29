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
from hummingbot.market.beaxy.beaxy_order_book_message import BeaxyOrderBookMessage


_bxob_logger = None


cdef class BeaxyOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _bxob_logger
        if _bxob_logger is None:
            _bxob_logger = logging.getLogger(__name__)
        return _bxob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return BeaxyOrderBookMessage
        (
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return BeaxyOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        if metadata:
            msg.update(metadata)
        ts = msg["timestamp"]
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["symbol"],
            "trade_type": float(TradeType.SELL.value) if msg["side"] == "SELL" else float(TradeType.BUY.value),
            "price": msg["price"],
            "update_id": ts,
            "amount": msg["size"]
        }, timestamp=ts * 1e-3)
