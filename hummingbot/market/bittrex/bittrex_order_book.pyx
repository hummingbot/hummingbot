#!/usr/bin/env python
import bz2
import ujson
from aiokafka import ConsumerRecord
from sqlalchemy.engine import RowProxy
from typing import (
    Optional,
    Dict
)

from wings.events import TradeType
from wings.order_book cimport OrderBook
from wings.order_book_message import OrderBookMessage, OrderBookMessageType
import logging
btob_logger = None


cdef class BittrexOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> logging.Logger:
        global btob_logger
        if btob_logger is None:
            btob_logger = logging.getLogger(__name__)
        return btob_logger

    @classmethod
    def snapshot_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record["timestamp"]
        msg = record["json"] if type(record["json"])==dict else ujson.loads(record["json"])
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "symbol": msg.get("symbol"),
            "update_id": ts,
            "bids": [[r["Rate"], r["Quantity"]] for r in msg["result"]["buy"]],
            "asks": [[r["Rate"], r["Quantity"]] for r in msg["result"]["sell"]]
        }, timestamp=ts * 1e-3)

    @classmethod
    def diff_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record["timestamp"]
        msg = record["json"] if type(record["json"])==dict else ujson.loads(record["json"])
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "symbol": msg["s"],
            "update_id": ts,
            "bids": msg["b"],
            "asks": msg["a"]
        }, timestamp=ts * 1e-3)

    @classmethod
    def snapshot_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record.timestamp
        msg = ujson.loads(record.value)
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "symbol": msg["symbol"],
            "update_id": ts,
            "bids": [[r["Rate"], r["Quantity"]] for r in msg["result"]["buy"]],
            "asks": [[r["Rate"], r["Quantity"]] for r in msg["result"]["sell"]]
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
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "symbol": msg["s"],
            "trade_type": float(TradeType.BUY.value) if msg["OT"] == "SELL"
                            else float(TradeType.SELL.value),
            "trade_id": ts,
            "update_id": ts,
            "price": msg["R"],
            "amount": msg["Q"]
        }, timestamp=ts * 1e-3)

    @classmethod
    def from_snapshot(cls, msg: OrderBookMessage) -> "OrderBook":
        retval = BittrexOrderBook()
        retval.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        return retval
