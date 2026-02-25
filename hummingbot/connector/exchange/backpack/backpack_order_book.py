"""Backpack order book implementation."""
from typing import Optional

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)


class BackpackOrderBook(OrderBook):
    """
    Order book implementation for Backpack Exchange.
    """

    @classmethod
    def snapshot_message_from_exchange(
        cls,
        msg: dict,
        timestamp: float,
        metadata: Optional[dict] = None,
    ) -> OrderBookMessage:
        """
        Creates a snapshot message from exchange data.
        
        :param msg: The snapshot data from exchange
        :param timestamp: The timestamp
        :param metadata: Optional metadata
        :return: OrderBookMessage
        """
        if metadata:
            msg.update(metadata)
        
        return OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content=msg,
            timestamp=timestamp,
        )

    @classmethod
    def diff_message_from_exchange(
        cls,
        msg: dict,
        timestamp: float,
        metadata: Optional[dict] = None,
    ) -> OrderBookMessage:
        """
        Creates a diff message from exchange data.
        
        :param msg: The diff data from exchange
        :param timestamp: The timestamp
        :param metadata: Optional metadata
        :return: OrderBookMessage
        """
        if metadata:
            msg.update(metadata)
        
        return OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content=msg,
            timestamp=timestamp,
        )

    @classmethod
    def trade_message_from_exchange(
        cls,
        msg: dict,
        metadata: Optional[dict] = None,
    ) -> OrderBookMessage:
        """
        Creates a trade message from exchange data.
        
        :param msg: The trade data from exchange
        :param metadata: Optional metadata
        :return: OrderBookMessage
        """
        if metadata:
            msg.update(metadata)
        
        return OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content=msg,
            timestamp=float(msg.get("T", 0)) / 1000,  # Convert ms to seconds
        )
