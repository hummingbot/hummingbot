#!/usr/bin/env python

import logging
from typing import (
    Dict,
    Optional,
)

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.market.kyber.kyber_order_book_message import KyberOrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType

_dob_logger = None


cdef class KyberOrderBook(OrderBook):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _dob_logger
        if _dob_logger is None:
            _dob_logger = logging.getLogger(__name__)
        return _dob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> KyberOrderBookMessage:
        if metadata:
            msg["data"]["orderBook"].update(metadata)
        return KyberOrderBookMessage(OrderBookMessageType.SNAPSHOT, msg["data"]["orderBook"], timestamp)
