#!/usr/bin/env python
from decimal import Decimal

from aiokafka import ConsumerRecord
import bz2
import logging
from sqlalchemy.engine import RowProxy
from typing import (
    Any,
    Optional,
    Dict
)
import ujson

from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType

_kuob_logger = None


cdef class KucoinOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _kuob_logger
        if _kuob_logger is None:
            _kuob_logger = logging.getLogger(__name__)
        return _kuob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, Any],
                                       timestamp: Optional[float] = None,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        msg_ts = int(msg["data"]["time"] * 1e-3)
        content = {
            "symbol": msg["symbol"],
            "update_id": msg_ts,
            "bids": msg["data"]["bids"],
            "asks": msg["data"]["asks"]
        }
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp or msg_ts)

    @classmethod
    def trade_message_from_exchange(cls,
                                   msg: Dict[str, Any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        msg_ts = msg["time"],
        content = {
            "symbol": msg["trading_pair"],
            "trade_type": float(TradeType.SELL.value) if msg["side"] == "buy" else float(TradeType.BUY.value),
            "trade_id": msg["tradeId"],
            "update_id": msg_ts,
            "amount": msg["size"],
            "price": msg["price"]
        }
        return OrderBookMessage(OrderBookMessageType.DIFF, content, timestamp or msg_ts)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, Any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        msg_ts = int(msg["ts"] * 1e-3)
        content = {
            "symbol": msg["data"]["symbol"],
            "update_id": msg_ts,
            "bids": msg["data"]["changes"]["bids"],
            "asks": msg["data"]["changes"]["asks"]
        }
        return OrderBookMessage(OrderBookMessageType.DIFF, content, timestamp or msg_ts)

    @classmethod
    def snapshot_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record["timestamp"]
        msg = record["json"] if type(record["json"])==dict else ujson.loads(record["json"])
        if metadata:
            msg.update(metadata)

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
			"symbol": msg["symbol"],
            "update_id": msg_ts,
            "bids": msg["data"]["bids"],
            "asks": msg["data"]["asks"]
        }, timestamp=ts * 1e-3)

    @classmethod
    def diff_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record["timestamp"]
        msg = record["json"] if type(record["json"])==dict else ujson.loads(record["json"])
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "symbol": msg["s"],
            "update_id": int(ts),
            "bids": msg["b"],
            "asks": msg["a"]
        }, timestamp=ts * 1e-3)

    @classmethod
    def snapshot_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record.timestamp
        msg = ujson.loads(record.value.decode())
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
			"symbol": msg["symbol"],
            "update_id": msg_ts,
            "bids": msg["data"]["bids"],
            "asks": msg["data"]["asks"]
        }, timestamp=ts * 1e-3)

    @classmethod
    def diff_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        decompressed = bz2.decompress(record.value)
        msg = ujson.loads(decompressed)
        ts = record.timestamp
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "symbol": msg["s"],
            "update_id": ts,
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=ts * 1e-3)

    @classmethod
    def trade_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        msg = record["json"]
        ts = record.timestamp
        data = msg["data"]
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "symbol": msg["symbol"]
            "trade_type": float(TradeType.BUY.value) if data["side"] == "buy"
                            else float(TradeType.SELL.value),
            "trade_id": ts,
            "update_id": ts,
            "price": data["price"],
            "amount": data["size"]
        }, timestamp=ts * 1e-3)

    @classmethod
    def from_snapshot(cls, msg: OrderBookMessage) -> "OrderBook":
        retval = KucoinOrderBook()
        retval.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        return retval
