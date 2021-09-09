#!/usr/bin/env python
import logging
from typing import (
    Dict,
    List,
    Optional,
)

import pandas as pd

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)

from hummingbot.connector.exchange.eterbase.eterbase_order_book_message import EterbaseOrderBookMessage

_eob_logger = None


cdef class EterbaseOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _eob_logger
        if _eob_logger is None:
            _eob_logger = logging.getLogger(__name__)
        return _eob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        *required
        Convert json snapshot data into standard OrderBookMessage format
        :param msg: json snapshot data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :return: EterbaseOrderBookMessage
        """
        if metadata:
            msg.update(metadata)
        return EterbaseOrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        *required
        Convert json diff data into standard OrderBookMessage format
        :param msg: json diff data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :return: EterbaseOrderBookMessage
        """
        if metadata:
            msg.update(metadata)

        msg_time=None
        if "time" in msg:
            msg_time = pd.Timestamp(msg["time"]).timestamp()

        eobm = EterbaseOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp or msg_time)

        return eobm

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError("Eterbase order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError("Eterbase order book needs to retain individual order data.")
