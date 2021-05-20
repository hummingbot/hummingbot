#!/usr/bin/env python

from aiokafka import ConsumerRecord
import logging
from sqlalchemy.engine import RowProxy
from typing import (
    Dict,
    List,
    Optional,
)
import ujson
from datetime import datetime

from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.dydx.dydx_order_book_message import DydxOrderBookMessage
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)

_dob_logger = None


cdef class DydxOrderBook(OrderBook):

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
                                       metadata: Optional[Dict] = None) -> DydxOrderBookMessage:
        if metadata:
            msg["id"] = int(timestamp * 1000)
            msg["market"] = metadata["id"]

        return DydxOrderBookMessage(OrderBookMessageType.SNAPSHOT, msg, timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg["market"] = metadata["id"]
        return DydxOrderBookMessage(OrderBookMessageType.DIFF, msg, timestamp)

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        time = msg["createdAt"]
        ts = datetime.timestamp(datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ"))
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": metadata["id"],
            "trade_type": float(TradeType.SELL.value) if (msg["side"] == "SELL") else float(TradeType.BUY.value),
            "trade_id": msg["uuid"],
            "update_id": ts,
            "price": msg["price"],
            "amount": msg["amount"]
        }, timestamp=ts)

    @classmethod
    def snapshot_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        msg = record.json if type(record.json) == dict else ujson.loads(record.json)
        return DydxOrderBookMessage(OrderBookMessageType.SNAPSHOT, msg, timestamp=record.timestamp * 1e-3)

    @classmethod
    def diff_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        return DydxOrderBookMessage(OrderBookMessageType.DIFF, record.json)

    @classmethod
    def snapshot_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        msg = ujson.loads(record.value.decode())
        return DydxOrderBookMessage(OrderBookMessageType.SNAPSHOT, msg, timestamp=record.timestamp * 1e-3)

    @classmethod
    def diff_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        msg = ujson.loads(record.value.decode())
        return DydxOrderBookMessage(OrderBookMessageType.DIFF, msg)

    @classmethod
    def trade_receive_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        return DydxOrderBookMessage(OrderBookMessageType.TRADE, record.json)

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError("dydx order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError("dydx order book needs to retain individual order data.")
