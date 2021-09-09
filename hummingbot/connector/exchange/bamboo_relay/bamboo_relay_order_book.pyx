#!/usr/bin/env python
import logging
from typing import (
    Dict,
    List,
    Optional
)

from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.bamboo_relay.bamboo_relay_order_book_message import BambooRelayOrderBookMessage
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)

_rrob_logger = None


cdef class BambooRelayOrderBook(OrderBook):

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _rrob_logger
        if _rrob_logger is None:
            _rrob_logger = logging.getLogger(__name__)
        return _rrob_logger

    def __init__(self):
        super().__init__(dex=True)

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return BambooRelayOrderBookMessage(OrderBookMessageType.SNAPSHOT, msg, timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return BambooRelayOrderBookMessage(OrderBookMessageType.DIFF, msg, timestamp)

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError("BambooRelay order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError("BambooRelay order book needs to retain individual order data.")
