import logging
from typing import (
    Dict,
    List,
    Optional,
)

import ujson
from aiokafka import ConsumerRecord

from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.loopring.loopring_order_book_message import LoopringOrderBookMessage
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)
from hummingbot.core.event.events import TradeType

_dob_logger = None

cdef class LoopringOrderBook(OrderBook):

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
                                       metadata: Optional[Dict] = None) -> LoopringOrderBookMessage:
        if metadata:
            msg.update(metadata)
        return LoopringOrderBookMessage(OrderBookMessageType.SNAPSHOT, msg, timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        if metadata:
            msg.update(metadata)
        return LoopringOrderBookMessage(OrderBookMessageType.DIFF, msg, timestamp)

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        ts = metadata["ts"]
        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": metadata["topic"]["market"],
            "trade_type": float(TradeType.SELL.value) if (msg[2] == "SELL") else float(TradeType.BUY.value),
            "trade_id": msg[1],
            "update_id": ts,
            "price": msg[4],
            "amount": msg[3]
        }, timestamp=ts * 1e-3)

    @classmethod
    def snapshot_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        msg = ujson.loads(record.value.decode())
        return LoopringOrderBookMessage(OrderBookMessageType.SNAPSHOT, msg, timestamp=record.timestamp * 1e-3)

    @classmethod
    def diff_message_from_kafka(cls, record: ConsumerRecord, metadata: Optional[Dict] = None) -> OrderBookMessage:
        msg = ujson.loads(record.value.decode())
        return LoopringOrderBookMessage(OrderBookMessageType.DIFF, msg)

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError("loopring order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError("loopring order book needs to retain individual order data.")
