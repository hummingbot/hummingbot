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
from hummingbot.connector.exchange.duedex.duedex_utils import convert_from_exchange_trading_pair

_orderbook_logger = None


cdef class DuedexOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _orderbook_logger
        if _orderbook_logger is None:
            _orderbook_logger = logging.getLogger(__name__)
        return _orderbook_logger

    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, Any],
                                    timestamp: Optional[float] = None,
                                    metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        content = {
            "trading_pair": convert_from_exchange_trading_pair(msg["instrument"]),
            "trade_type": float(TradeType.BUY.value) if msg["side"] == "long" else float(TradeType.SELL.value),
            "trade_id": msg["matchId"],
            "update_id": msg["sequence"],
            "amount": msg["size"],
            "price": msg["price"]
        }
        return OrderBookMessage(OrderBookMessageType.TRADE, content, timestamp)

    @classmethod
    def trade_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        msg = record["json"]
        ts = record.timestamp
        data = msg["data"]
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": convert_from_exchange_trading_pair(msg["instrument"]),
            "trade_type": float(TradeType.BUY.value) if data["side"] == "long" else float(TradeType.SELL.value),
            "trade_id": msg["matchId"],
            "update_id": msg["sequence"],
            "price": data["price"],
            "amount": data["size"]
        }, timestamp=ts)

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, Any],
                                       timestamp: Optional[float] = None,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        content = {
            "trading_pair": convert_from_exchange_trading_pair(msg["instrument"]),
            "update_id": msg["sequence"],
            "bids": msg["bids"],
            "asks": msg["asks"]
        }
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, Any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        content = {
            "trading_pair": convert_from_exchange_trading_pair(msg["instrument"]),
            "update_id": msg["sequence"],
            "bids": msg["bids"],
            "asks": msg["asks"]
        }
        return OrderBookMessage(OrderBookMessageType.DIFF, content, timestamp)

    @classmethod
    def snapshot_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record["timestamp"]
        msg = record["json"] if type(record["json"])==dict else ujson.loads(record["json"])
        if metadata:
            msg.update(metadata)

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": convert_from_exchange_trading_pair(msg["instrument"]),
            "update_id": msg["sequence"],
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=ts)

    @classmethod
    def diff_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record["timestamp"]
        msg = record["json"] if type(record["json"])==dict else ujson.loads(record["json"])
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": convert_from_exchange_trading_pair(msg["instrument"]),
            "update_id": msg["sequence"],
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=ts)

    @classmethod
    def snapshot_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record.timestamp
        msg = ujson.loads(record.value.decode())
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": convert_from_exchange_trading_pair(msg["instrument"]),
            "update_id": msg["sequence"],
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=ts)

    @classmethod
    def diff_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        decompressed = bz2.decompress(record.value)
        msg = ujson.loads(decompressed)
        ts = record.timestamp
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": convert_from_exchange_trading_pair(msg["instrument"]),
            "update_id": msg["sequence"],
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=ts)

    @classmethod
    def from_snapshot(cls, msg: OrderBookMessage) -> "OrderBook":
        retval = DuedexOrderBook()
        retval.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        return retval
