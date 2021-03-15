import ujson
import logging
import time
from typing import (
    Dict,
    List,
    Optional,
    Any,
)

from sqlalchemy.engine import RowProxy
import pandas as pd

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)
from hummingbot.connector.exchange.idex.idex_order_book_message import IdexOrderBookMessage

_iob_logger = None


cdef class IdexOrderBook(OrderBook):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _iob_logger
        if _iob_logger is None:
            _iob_logger = logging.getLogger(__name__)
        return _iob_logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, Any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        *required
        Convert JSON snapshot data into standard OrderBookMessage format
        :param msg: json snapshot data from api fetch request or live web socket stream
        :param timestamp: timestamp attached to incoming data
        :return: IdexOrderBookMessage
        """
        if metadata:
            msg.update(metadata)
        return IdexOrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, Any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        *required
        Convert json diff data into standard OrderBookMessage format
        :param msg: json diff data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :return: IdexOrderBookMessage
        """

        if metadata:
            msg.update(metadata)
        if msg.get("data").get("t") is None:
            # time is present in msg as msg["data"]["t"] in POSIX format. If not, call time.time() for UTC/s timestamp
            msg_time = time.time()
        return IdexOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp or msg_time)

    @classmethod
    def snapshot_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        *used for backtesting
        Convert a row of snapshot data into standard OrderBookMessage format
        :param record: a row of snapshot data from the database
        :return: IdexOrderBookMessage
        """
        msg = record.json if type(record.json) == dict else ujson.loads(record.json)  # TODO ALF: check not cb specific
        return IdexOrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=record.timestamp * 1e-3  # TODO ALF: check not cb specific
        )

    @classmethod
    def diff_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        *used for backtesting
        Convert a row of diff data into standard OrderBookMessage format
        :param record: a row of diff data from the database
        :return: IdexOrderBookMessage
        """
        return IdexOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=record.json,
            timestamp=record.timestamp * 1e-3
        )

    @classmethod
    def trade_receive_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        """
        *used for backtesting
        Convert a row of trade data into standard OrderBookMessage format
        :param record: a row of trade data from the database
        :return: IdexOrderBookMessage
        """
        return IdexOrderBookMessage(
            OrderBookMessageType.TRADE,
            record.json,
            timestamp=record.timestamp * 1e-3
        )

    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, Any],
                                    timestamp: Optional[float] = None,
                                    metadata: Optional[Dict] = None):
        """
        Convert a trade data into standard OrderBookMessage format
        :param msg: json diff data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :param metadata: metadata to add to the websocket message
        :return: IdexOrderBookMessage
        """
        # msg keys taken from ws trade response
        if metadata:
            msg.update(metadata)
        msg.update({
            "exchange_order_id": msg.get("data").get("i"),
            "trade_type": msg.get("data").get("s"),
            "price": msg.get("data").get("p"),
            "amount": msg.get("data").get("q"),
        })
        return IdexOrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError("Idex orderbook needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(self, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError("Idex orderbook needs to retain individual order data.")
