#!/usr/bin/env python

import logging
from sqlalchemy.engine import RowProxy
from typing import (
    Dict,
    List,
    Optional
)
import ujson

from hummingbot.logger import HummingbotLogger
from hummingbot.market.idex.idex_order_book_message import IDEXOrderBookMessage
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)

_iob_logger = None


cdef class IDEXOrderBook(OrderBook):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _iob_logger
        if _iob_logger is None:
            _iob_logger = logging.getLogger(__name__)
        return _iob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: Optional[float] = None,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return IDEXOrderBookMessage(OrderBookMessageType.SNAPSHOT, msg, timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return IDEXOrderBookMessage(OrderBookMessageType.DIFF, msg, timestamp)

    @classmethod
    def snapshot_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        msg = record.json if type(record.json)==dict else ujson.loads(record.json)
        return IDEXOrderBookMessage(OrderBookMessageType.SNAPSHOT, msg,
                                    timestamp=record.timestamp * 1e-3)

    @classmethod
    def diff_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        return IDEXOrderBookMessage(OrderBookMessageType.DIFF, record.json)

    @classmethod
    def trade_receive_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        return IDEXOrderBookMessage(OrderBookMessageType.TRADE, record.json)

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError("IDEX order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError("IDEX order book needs to retain individual order data.")
