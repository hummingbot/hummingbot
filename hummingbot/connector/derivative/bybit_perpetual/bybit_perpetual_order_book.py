import logging
from decimal import Decimal

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)
from hummingbot.core.event.events import TradeType
from hummingbot.logger import HummingbotLogger


class BybitPerpetualOrderBook(OrderBook):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    def _bids_and_asks_from_entries(cls, entries: List[Dict[str, Any]]):
        bids = []
        asks = []
        for entry in entries:
            amount = Decimal(entry["size"]) if "size" in entry else Decimal("0")
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

        entries = msg["data"]["order_book"] if "order_book" in msg["data"] else msg["data"]
        bids, asks = cls._bids_and_asks_from_entries(entries)

        msg.update({"asks": asks,
                    "bids": bids,
                    "update_id": int(msg["timestamp_e6"])})

        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=timestamp
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

        all_entries = []

        all_entries.extend(msg["data"]["delete"])
        all_entries.extend(msg["data"]["update"])
        all_entries.extend(msg["data"]["insert"])

        bids, asks = cls._bids_and_asks_from_entries(all_entries)

        bids.sort(key=lambda entry_data: entry_data[0])
        asks.sort(key=lambda entry_data: entry_data[0])

        msg.update({"asks": asks,
                    "bids": bids,
                    "update_id": int(msg["timestamp_e6"])})

        return OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp
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
    def from_snapshot(cls, snapshot: OrderBookMessage):
        raise NotImplementedError(CONSTANTS.EXCHANGE_NAME + " order book needs to retain individual order data.")

    @classmethod
    def restore_from_snapshot_and_diffs(cls, snapshot: OrderBookMessage, diffs: List[OrderBookMessage]):
        raise NotImplementedError(CONSTANTS.EXCHANGE_NAME + " order book needs to retain individual order data.")
