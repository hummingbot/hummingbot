#!/usr/bin/env python
import ujson
import logging
from typing import (
    Dict,
    List,
    Optional,
)

from sqlalchemy.engine import RowProxy
import pandas as pd

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import (
<<<<<<< HEAD
    bitroyalOrderBookMessage,
=======
    CoinbaseProOrderBookMessage,
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
    OrderBookMessage,
    OrderBookMessageType
)

_cbpob_logger = None


<<<<<<< HEAD
cdef class bitroyalOrderBook(OrderBook):
=======
cdef class CoinbaseProOrderBook(OrderBook):
>>>>>>> Created bitroyal connector folder and files in hummingbot>market

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _cbpob_logger
        if _cbpob_logger is None:
            _cbpob_logger = logging.getLogger(__name__)
        return _cbpob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
<<<<<<< HEAD
        return bitroyalOrderBookMessage(
=======
        return CoinbaseProOrderBookMessage(
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
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
        if "time" in msg:
            msg_time = pd.Timestamp(msg["time"]).timestamp()
<<<<<<< HEAD
        return bitroyalOrderBookMessage(
=======
        return CoinbaseProOrderBookMessage(
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp or msg_time)

    @classmethod
    def snapshot_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        msg = record.json if type(record.json)==dict else ujson.loads(record.json)
<<<<<<< HEAD
        return bitroyalOrderBookMessage(
=======
        return CoinbaseProOrderBookMessage(
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=record.timestamp * 1e-3
        )

    @classmethod
    def diff_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
<<<<<<< HEAD
        return bitroyalOrderBookMessage(
=======
        return CoinbaseProOrderBookMessage(
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
            message_type=OrderBookMessageType.DIFF,
            content=record.json,
            timestamp=record.timestamp * 1e-3
        )

    @classmethod
    def trade_receive_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
<<<<<<< HEAD
        return bitroyalOrderBookMessage(
=======
        return CoinbaseProOrderBookMessage(
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
            OrderBookMessageType.TRADE,
            record.json,
            timestamp=record.timestamp * 1e-3
        )

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
<<<<<<< HEAD
        raise NotImplementedError("Bitroyal order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError("Bitroyal order book needs to retain individual order data.")
=======
        raise NotImplementedError("Coinbase Pro order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError("Coinbase Pro order book needs to retain individual order data.")
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
