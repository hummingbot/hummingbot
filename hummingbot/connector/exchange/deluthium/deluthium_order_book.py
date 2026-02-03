"""
Order book implementation for Deluthium DEX connector.

Note: Deluthium is RFQ-based, so there's no traditional order book.
This class handles quote-based pricing from indicative quotes.
"""

from typing import Dict, Optional

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class DeluthiumOrderBook(OrderBook):
    """
    Deluthium order book implementation.
    
    Since Deluthium is RFQ-based, this handles quote snapshots
    rather than traditional order book depth.
    """

    @classmethod
    def snapshot_message_from_exchange(
        cls,
        msg: Dict[str, any],
        timestamp: float,
        metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        """
        Create a snapshot message from exchange data.
        """
        if metadata:
            msg.update(metadata)
        
        trading_pair = msg.get("trading_pair", "")
        update_id = int(msg.get("update_id", timestamp * 1000))
        
        bids = msg.get("bids", [])
        asks = msg.get("asks", [])
        
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp
        )

    @classmethod
    def diff_message_from_exchange(
        cls,
        msg: Dict[str, any],
        timestamp: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        """Create a diff message from exchange data."""
        if metadata:
            msg.update(metadata)
        
        trading_pair = msg.get("trading_pair", "")
        update_id = msg.get("update_id", int(timestamp * 1000) if timestamp else 0)
        
        bids = msg.get("bids", [])
        asks = msg.get("asks", [])
        
        return OrderBookMessage(
            OrderBookMessageType.DIFF,
            {
                "trading_pair": trading_pair,
                "update_id": update_id,
                "bids": bids,
                "asks": asks,
            },
            timestamp=timestamp
        )

    @classmethod
    def trade_message_from_exchange(
        cls,
        msg: Dict[str, any],
        metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        """Create a trade message from exchange data."""
        if metadata:
            msg.update(metadata)
        
        trading_pair = msg.get("trading_pair", "")
        trade_type = TradeType.BUY if msg.get("side", "").lower() == "buy" else TradeType.SELL
        trade_id = msg.get("trade_id", msg.get("quote_id", ""))
        price = float(msg.get("price", 0))
        amount = float(msg.get("amount", 0))
        timestamp = msg.get("timestamp", 0)
        
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": trading_pair,
                "trade_type": float(trade_type.value),
                "trade_id": trade_id,
                "price": price,
                "amount": amount,
            },
            timestamp=timestamp
        )
