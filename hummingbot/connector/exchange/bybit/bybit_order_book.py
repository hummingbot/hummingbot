import logging
from decimal import Decimal

import hummingbot.connector.exchange.bybit.bybit_constants as CONSTANTS

from sqlalchemy.engine import RowProxy
from typing import (
    Optional,
    Dict,
    List, Any)

from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage, OrderBookMessageType
)


class BybitOrderBook(OrderBook):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    def _bids_and_asks_from_entries(cls, entries: List[Dict[str, Any]], predetermined_amount: Optional[Decimal] = None):
        bids = []
        asks = []
        for entry in entries:
            amount = Decimal(entry["size"] if predetermined_amount is None else predetermined_amount)
            entry_data = [Decimal(entry["price"]), amount]
            if entry["side"].upper() == TradeType.SELL.name:
                asks.append(entry_data)
            else:
                bids.append(entry_data)

        return bids, asks

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None):
        """
        Convert json snapshot data into standard OrderBookMessage format
        :param msg: json snapshot data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :param metadata: extra information
        :return: OrderBookMessage
        """

        if metadata:
            msg.update(metadata)

        bids, asks = cls._bids_and_asks_from_entries(msg["data"])

        msg.update({"asks": asks,
                    "bids": bids,
                    "update_id": msg["timestamp_e6"]})

        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def snapshot_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        """
        *used for backtesting
        Convert a row of snapshot data into standard OrderBookMessage format
        :param record: a row of snapshot data from the database
        :param metadata: extra information
        :return: OrderBookMessage
        """
        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=record.json,
            timestamp=record.timestamp
        )

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None):
        """
        Convert json diff data into standard OrderBookMessage format
        :param msg: json diff data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :param metadata: extra information
        :return: OrderBookMessage
        """

        if metadata:
            msg.update(metadata)

        asks = []
        bids = []

        bids_to_delete, asks_to_delete = cls._bids_and_asks_from_entries(entries=msg["data"]["delete"],
                                                                         predetermined_amount=Decimal("0"))
        bids.extend(bids_to_delete)
        asks.extend(asks_to_delete)

        bids_to_update, asks_to_update = cls._bids_and_asks_from_entries(entries=msg["data"]["update"])
        bids.extend(bids_to_update)
        asks.extend(asks_to_update)

        bids_to_insert, asks_to_insert = cls._bids_and_asks_from_entries(entries=msg["data"]["insert"])
        bids.extend(bids_to_insert)
        asks.extend(asks_to_insert)

        bids.sort(key=lambda entry_data: entry_data[0])
        asks.sort(key=lambda entry_data: entry_data[0])

        msg.update({"asks": asks,
                    "bids": bids,
                    "update_id": msg["timestamp_e6"]})

        return OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def diff_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        """
        *used for backtesting
        Convert a row of diff data into standard OrderBookMessage format
        :param record: a row of diff data from the database
        :param metadata: extra information
        :return: OrderBookMessage
        """
        return OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=record.json,
            timestamp=record.timestamp
        )

    @classmethod
    def trade_message_from_exchange(cls,
                                    msg: Dict[str, Any],
                                    timestamp: Optional[float] = None,
                                    metadata: Optional[Dict] = None):
        """
        Convert a trade data into standard OrderBookMessage format
        :param msg: json trade data from live web socket stream
        :param timestamp: timestamp attached to incoming data
        :param metadata: extra information
        :return: OrderBookMessage
        """

        if metadata:
            msg.update(metadata)

        # Data fields are obtained from OrderTradeEvents
        msg.update({
            "trade_type": float(TradeType.BUY.value
                                if msg.get("side").upper() == TradeType.BUY.name
                                else TradeType.SELL.value),
            "amount": msg.get("size"),
            "asks": [],
            "bids": [],
        })

        return OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=msg,
            timestamp=timestamp
        )

    @classmethod
    def trade_message_from_db(cls, record: RowProxy, metadata: Optional[Dict] = None):
        """
        *used for backtesting
        Convert a row of trade data into standard OrderBookMessage format
        :param record: a row of trade data from the database
        :param metadata: extra information
        :return: OrderBookMessage
        """
        return OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=record.json,
            timestamp=record.timestamp
        )

    @classmethod
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError(CONSTANTS.EXCHANGE_NAME + " order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(cls, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError(CONSTANTS.EXCHANGE_NAME + " order book needs to retain individual order data.")
