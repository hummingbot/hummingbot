from typing import Dict, Optional

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType,
)


class KuruOrderBook(OrderBook):
    """
    Kuru-specific OrderBook.

    Kuru sends full orderbook snapshots (not incremental diffs),
    so this subclass only provides snapshot message creation.
    """

    @classmethod
    def snapshot_message_from_exchange(
        cls,
        msg: Dict[str, any],
        timestamp: float,
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        """
        Create an OrderBookMessage SNAPSHOT from Kuru orderbook data.

        Args:
            msg: Dict with keys:
                - "trading_pair": str
                - "update_id": int (monotonically increasing)
                - "bids": [[price, amount], ...]
                - "asks": [[price, amount], ...]
            timestamp: Message timestamp
            metadata: Optional metadata to merge into msg

        Returns:
            OrderBookMessage of type SNAPSHOT
        """
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": msg["trading_pair"],
                "update_id": msg["update_id"],
                "bids": msg["bids"],
                "asks": msg["asks"],
            },
            timestamp=timestamp,
        )

    @classmethod
    def trade_message_from_exchange(
        cls,
        msg: Dict[str, any],
        metadata: Optional[Dict] = None,
    ) -> OrderBookMessage:
        """
        Create an OrderBookMessage TRADE from a Kuru trade event.

        Args:
            msg: Dict with keys:
                - "trading_pair": str
                - "trade_type": float (TradeType value)
                - "trade_id": str
                - "price": float
                - "amount": float
                - "timestamp": float
            metadata: Optional metadata to merge

        Returns:
            OrderBookMessage of type TRADE
        """
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg["trading_pair"],
                "trade_type": msg["trade_type"],
                "trade_id": msg["trade_id"],
                "price": msg["price"],
                "amount": msg["amount"],
            },
            timestamp=msg["timestamp"],
        )
