import bz2
import logging
from typing import (
    Any,
    Optional,
    Dict
)

from aiokafka import ConsumerRecord
import ujson

from hummingbot.connector.exchange.huobi.huobi_utils import convert_from_exchange_trading_pair
from hummingbot.core.event.events import TradeType
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.logger import HummingbotLogger

_hob_logger = None


cdef class HuobiOrderBook(OrderBook):
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
            msg.update(metadata)
        msg_ts = timestamp or int(msg["tick"]["ts"])
        content = {
            "trading_pair": convert_from_exchange_trading_pair(msg["trading_pair"]),
            "update_id": msg_ts,
            "bids": msg["tick"]["bids"],
            "asks": msg["tick"]["asks"]
        }
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp or msg_ts)

    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, Any],
                                    timestamp: Optional[float] = None,
                                    metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        msg_ts = timestamp or int(msg["ts"])
        content = {
            "trading_pair": convert_from_exchange_trading_pair(msg["trading_pair"]),
            "trade_type": float(TradeType.SELL.value) if msg["direction"] == "buy" else float(TradeType.BUY.value),
            "trade_id": msg["id"],
            "update_id": msg_ts,
            "amount": msg["amount"],
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
        msg_ts = timestamp or int(msg["tick"]["ts"])
        content = {
            "trading_pair": convert_from_exchange_trading_pair(msg["ch"].split(".")[1]),
            "update_id": msg_ts,
            "bids": msg["tick"]["bids"],
            "asks": msg["tick"]["asks"]
        }
        return OrderBookMessage(OrderBookMessageType.DIFF, content, timestamp or msg_ts)

    @classmethod
    def snapshot_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        ts = record.timestamp
        msg = ujson.loads(record.value.decode())
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": convert_from_exchange_trading_pair(msg["ch"].split(".")[1]),
            "update_id": ts,
            "bids": msg["tick"]["bids"],
            "asks": msg["tick"]["asks"]
        }, timestamp=ts)

    @classmethod
    def diff_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        decompressed = bz2.decompress(record.value)
        msg = ujson.loads(decompressed)
        ts = record.timestamp
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.DIFF, {
            "trading_pair": convert_from_exchange_trading_pair(msg["s"]),
            "update_id": ts,
            "bids": msg["bids"],
            "asks": msg["asks"]
        }, timestamp=ts)

    @classmethod
    def from_snapshot(cls, msg: OrderBookMessage) -> "OrderBook":
        retval = HuobiOrderBook()
        retval.apply_snapshot(msg.bids, msg.asks, msg.update_id)
        return retval
