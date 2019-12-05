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

_hob_logger = None


cdef class KrakenOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _hob_logger
        if _hob_logger is None:
            _hob_logger = logging.getLogger(__name__)
        return _hob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, Any],
                                       timestamp: Optional[float] = None,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
<<<<<<< HEAD
            bids = msg["bids"]
            asks = msg["asks"]
            symbol = metadata["symbol"]
        else:
            bids = msg[1]["bs"]
            asks = msg[1]["as"]
            symbol = msg[-1]
        content = {
            "symbol": symbol,
            "update_id": timestamp,
            "bids": bids,
            "asks": asks
=======
            msg.update(metadata)
        content = {
            "symbol": msg["symbol"],
            "update_id": timestamp,
            "bids": msg["bids"],
            "asks": msg["asks"]
>>>>>>> kraken
        }
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp)

    @classmethod
    def trade_message_from_exchange(cls,
                                   msg: Dict[str, Any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        msg_ts = int(float(msg[2]))
        content = {
            "symbol": metadata["symbol"],
            "trade_type": float(TradeType.SELL.value) if msg[3] == "s" else float(TradeType.BUY.value),
            "trade_id": msg_ts,
            "update_id": msg_ts,
            "amount": msg[1],
            "price": msg[0]
        }
        return OrderBookMessage(OrderBookMessageType.TRADE, content, timestamp or msg_ts)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, Any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        content = {
            "symbol": msg[3],
            "update_id": timestamp,
            "bids": msg[1]["b"] if "b" in msg[1] else [],
            "asks": msg[1]["a"] if "a" in msg[1] else []
        }
        return OrderBookMessage(OrderBookMessageType.DIFF, content, timestamp)

    @classmethod
    def snapshot_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record["timestamp"]
        msg = record["json"] if type(record["json"])==dict else ujson.loads(record["json"])
        if metadata:
            msg.update(metadata)

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "symbol": msg["symbol"],
            "update_id": ts,
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=ts * 1e-3)

    @classmethod
    def diff_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record["timestamp"]
        msg = record["json"] if type(record["json"])==dict else ujson.loads(record["json"])
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "symbol": msg[3],
            "update_id": ts,
            "bids": msg[1]["b"] if "b" in msg[1] else [],
            "asks": msg[1]["a"] if "a" in msg[1] else []
        }, timestamp=ts * 1e-3)

    @classmethod
    def snapshot_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record.timestamp
        msg = ujson.loads(record.value.decode())
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "symbol": msg["symbol"],
            "update_id": ts,
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=ts * 1e-3)

    @classmethod
    def diff_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        decompressed = bz2.decompress(record.value)
        msg = ujson.loads(decompressed)
        ts = record.timestamp
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "symbol": msg[3],
            "update_id": ts,
            "bids": msg[1]["b"] if "b" in msg[1] else [],
            "asks": msg[1]["a"] if "a" in msg[1] else []
        }, timestamp=ts * 1e-3)

    @classmethod
    def trade_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        msg = record["json"]
        ts = record.timestamp
        data = msg["tick"]["data"][0]
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "symbol": msg["pair"],
            "trade_type": float(TradeType.SELL.value) if msg[3] == "s" else float(TradeType.BUY.value),
            "trade_id": ts,
            "update_id": ts,
            "amount": msg[1],
            "price": msg[0]
        }, timestamp=ts * 1e-3)

    @classmethod
    def from_snapshot(cls, msg: OrderBookMessage) -> "OrderBook":
        retval = KrakenOrderBook()
        retval.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        return retval
