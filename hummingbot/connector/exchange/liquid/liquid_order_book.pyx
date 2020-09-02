#!/usr/bin/env python
import logging
from typing import (
    Dict,
    Optional,
)

from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.connector.exchange.liquid.liquid_order_book_message import LiquidOrderBookMessage


cdef class LiquidOrderBook(OrderBook):

    @classmethod
    def logger(cls):
        global lob_logger
        if lob_logger is None:
            lob_logger = logging.getLogger(__name__)
        return lob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> (OrderBookMessage):
        """
        *required
        Convert json snapshot data into standard OrderBookMessage format
        :param msg: json snapshot data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :param metadata:
        :return: LiquidOrderBookMessage
        """
        if metadata:
            msg.update(metadata)
        return LiquidOrderBookMessage(
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
        :param metadata:
        :return: LiquidOrderBookMessage
        """
        if metadata:
            msg.update(metadata)
        return LiquidOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp
        )
