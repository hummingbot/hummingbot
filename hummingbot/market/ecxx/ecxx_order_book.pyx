#!/usr/bin/env python
import logging
import pandas as pd
import logging

from typing import (
    Optional,
    List,
    Dict,
    Any
)
import ujson
from sqlalchemy.engine import RowProxy

from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType

_ecob_logger = None

cdef class EcxxOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _ecob_logger
        if _ecob_logger is None:
            _ecob_logger = logging.getLogger(__name__)
        return _ecob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None):
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, Any],
                                    timestamp: Optional[float] = None,
                                    metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        msg_ts = int(msg)

    @classmethod
    def snapshot_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:

        msg = record.json if type(record.json)==dict else ujson.loads(record.json)
        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=record.timestamp * 1e-3
        )

    @classmethod
    def diff_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        return OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=record.json,
            timestamp=record.timestamp * 1e-3
        )

    @classmethod
    def trade_receive_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        """
        *used for backtesting
        Convert a row of trade data into standard OrderBookMessage format
        :param record: a row of trade data from the database
        :return: CoinbaseProOrderBookMessage
        """
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            record.json,
            timestamp=record.timestamp * 1e-3
        )

    @classmethod
    def from_snapshot(cls, msg: OrderBookMessage) -> "OrderBook":
        retval = OrderBook()
        retval.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        return retval
