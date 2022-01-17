import bz2
import logging
from typing import (
    Any,
    Dict,
    Optional,
)

from aiokafka import ConsumerRecord
import ujson

from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger

_okexob_logger = None


cdef class OkexOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _okexob_logger
        if _okexob_logger is None:
            _okexob_logger = logging.getLogger(__name__)
        return _okexob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, Any],
                                       trading_pair: str,
                                       timestamp: Optional[float] = None,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        msg_ts = int(msg["ts"] * 1e-3)  # TODO is this required?
        content = {
            "trading_pair": trading_pair,
            "update_id": msg_ts,
            "bids": msg["bids"],
            "asks": msg["asks"]
        }
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp or msg_ts)

    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, Any],
                                    timestamp: Optional[float] = None,
                                    metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        msg_ts = int(timestamp * 1e-3)  # TODO is this required?
        content = {
            "trading_pair": msg["trading_pair"],
            "trade_type": float(TradeType.SELL.value) if msg["side"] == "buy" else float(TradeType.BUY.value),
            "trade_id": msg["trade_id"],
            "update_id": msg_ts,
            "amount": msg["size"],
            "price": msg["price"]
        }
        return OrderBookMessage(OrderBookMessageType.DIFF, content, timestamp or msg_ts)

    @classmethod
    def diff_message_from_exchange(cls,
                                   data: Dict[str, Any],
                                   timestamp: float = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            data.update(metadata)

        msg_ts = int(timestamp * 1e-3)

        content = {
            "trading_pair": data["instId"],
            "update_id": msg_ts,
            "bids": data["bids"],
            "asks": data["asks"]
        }
        return OrderBookMessage(OrderBookMessageType.DIFF, content, timestamp or msg_ts)

    @classmethod
    def snapshot_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record.timestamp
        msg = ujson.loads(record.value.decode())
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["ch"].split(".")[1],
            "update_id": ts,
            "bids": msg["tick"]["bids"],
            "asks": msg["tick"]["asks"]
        }, timestamp=ts * 1e-3)

    @classmethod
    def diff_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        decompressed = bz2.decompress(record.value)
        msg = ujson.loads(decompressed)
        ts = record.timestamp
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": msg["s"],
            "update_id": ts,
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=ts * 1e-3)

    @classmethod
    def from_snapshot(cls, msg: OrderBookMessage) -> "OrderBook":
        retval = OkexOrderBook()
        retval.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        return retval
