"""
Order book message data types for Hummingbot framework.
Handles order book snapshots, updates, and trade messages.
"""

import time
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


class OrderBookMessageType(Enum):
    """
    Types of order book messages.
    """
    SNAPSHOT = "SNAPSHOT"
    DIFF = "DIFF"
    TRADE = "TRADE"


@dataclass
class OrderBookMessage:
    """
    Represents an order book message (snapshot, diff, or trade).
    
    This class encapsulates order book data from exchanges including
    snapshots, incremental updates, and trade information.
    """
    
    type: OrderBookMessageType
    content: Dict[str, Any]
    timestamp: float
    
    def __post_init__(self):
        """Post-initialization validation."""
        if not isinstance(self.timestamp, (int, float)):
            self.timestamp = float(self.timestamp)
        
        # Ensure content is a dictionary
        if not isinstance(self.content, dict):
            raise ValueError("Order book message content must be a dictionary")
    
    @property
    def trading_pair(self) -> str:
        """Get the trading pair for this message."""
        return self.content.get("trading_pair", "")
    
    @property
    def update_id(self) -> int:
        """Get the update ID for this message."""
        return self.content.get("update_id", 0)
    
    @property
    def bids(self) -> List[List[Decimal]]:
        """Get the bids from this message."""
        return self.content.get("bids", [])
    
    @property
    def asks(self) -> List[List[Decimal]]:
        """Get the asks from this message."""
        return self.content.get("asks", [])
    
    @property
    def trade_id(self) -> Optional[str]:
        """Get the trade ID if this is a trade message."""
        return self.content.get("trade_id")
    
    @property
    def price(self) -> Optional[Decimal]:
        """Get the trade price if this is a trade message."""
        price = self.content.get("price")
        return Decimal(str(price)) if price is not None else None
    
    @property
    def amount(self) -> Optional[Decimal]:
        """Get the trade amount if this is a trade message."""
        amount = self.content.get("amount")
        return Decimal(str(amount)) if amount is not None else None
    
    @property
    def trade_type(self) -> Optional[str]:
        """Get the trade type (buy/sell) if this is a trade message."""
        return self.content.get("trade_type")
    
    def has_update_id(self) -> bool:
        """Check if this message has an update ID."""
        return "update_id" in self.content and self.content["update_id"] > 0
    
    def has_trade_data(self) -> bool:
        """Check if this message contains trade data."""
        return self.type == OrderBookMessageType.TRADE and "price" in self.content
    
    def has_order_book_data(self) -> bool:
        """Check if this message contains order book data."""
        return self.type in [OrderBookMessageType.SNAPSHOT, OrderBookMessageType.DIFF] and \
               ("bids" in self.content or "asks" in self.content)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary representation."""
        return {
            "type": self.type.value,
            "content": self.content,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderBookMessage':
        """Create message from dictionary representation."""
        return cls(
            type=OrderBookMessageType(data["type"]),
            content=data["content"],
            timestamp=data["timestamp"]
        )
    
    @classmethod
    def snapshot_message(cls, 
                        trading_pair: str,
                        bids: List[List[Decimal]], 
                        asks: List[List[Decimal]],
                        update_id: int = 0,
                        timestamp: Optional[float] = None) -> 'OrderBookMessage':
        """
        Create an order book snapshot message.
        
        Args:
            trading_pair: Trading pair symbol
            bids: List of bid entries [price, quantity]
            asks: List of ask entries [price, quantity]
            update_id: Update ID for tracking
            timestamp: Message timestamp (defaults to current time)
            
        Returns:
            OrderBookMessage instance
        """
        if timestamp is None:
            timestamp = time.time() * 1000  # Convert to milliseconds
        
        content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": bids,
            "asks": asks
        }
        
        return cls(OrderBookMessageType.SNAPSHOT, content, timestamp)
    
    @classmethod
    def diff_message(cls,
                    trading_pair: str,
                    bids: List[List[Decimal]],
                    asks: List[List[Decimal]],
                    update_id: int,
                    timestamp: Optional[float] = None) -> 'OrderBookMessage':
        """
        Create an order book diff message.
        
        Args:
            trading_pair: Trading pair symbol
            bids: List of bid updates [price, quantity]
            asks: List of ask updates [price, quantity]
            update_id: Update ID for tracking
            timestamp: Message timestamp (defaults to current time)
            
        Returns:
            OrderBookMessage instance
        """
        if timestamp is None:
            timestamp = time.time() * 1000  # Convert to milliseconds
        
        content = {
            "trading_pair": trading_pair,
            "update_id": update_id,
            "bids": bids,
            "asks": asks
        }
        
        return cls(OrderBookMessageType.DIFF, content, timestamp)
    
    @classmethod
    def trade_message(cls,
                     trading_pair: str,
                     trade_type: str,
                     price: Decimal,
                     amount: Decimal,
                     trade_id: str,
                     timestamp: Optional[float] = None) -> 'OrderBookMessage':
        """
        Create a trade message.
        
        Args:
            trading_pair: Trading pair symbol
            trade_type: Trade type ("buy" or "sell")
            price: Trade price
            amount: Trade amount
            trade_id: Unique trade identifier
            timestamp: Trade timestamp (defaults to current time)
            
        Returns:
            OrderBookMessage instance
        """
        if timestamp is None:
            timestamp = time.time() * 1000  # Convert to milliseconds
        
        content = {
            "trading_pair": trading_pair,
            "trade_type": trade_type,
            "price": price,
            "amount": amount,
            "trade_id": trade_id
        }
        
        return cls(OrderBookMessageType.TRADE, content, timestamp)
    
    def __str__(self) -> str:
        """String representation of the message."""
        if self.type == OrderBookMessageType.SNAPSHOT:
            bids_count = len(self.bids)
            asks_count = len(self.asks)
            return f"OrderBookSnapshot({self.trading_pair}: {bids_count} bids, {asks_count} asks, update_id: {self.update_id})"
        elif self.type == OrderBookMessageType.DIFF:
            bids_count = len(self.bids)
            asks_count = len(self.asks)
            return f"OrderBookDiff({self.trading_pair}: {bids_count} bid updates, {asks_count} ask updates, update_id: {self.update_id})"
        elif self.type == OrderBookMessageType.TRADE:
            return f"Trade({self.trading_pair}: {self.trade_type} {self.amount} @ {self.price}, id: {self.trade_id})"
        else:
            return f"OrderBookMessage({self.type.value}: {self.trading_pair})"
    
    def __repr__(self) -> str:
        """Detailed representation of the message."""
        return f"OrderBookMessage(type={self.type.value}, trading_pair='{self.trading_pair}', timestamp={self.timestamp})"


# Utility functions for order book message handling
def validate_order_book_data(bids: List[List], asks: List[List]) -> bool:
    """
    Validate order book data format.
    
    Args:
        bids: List of bid entries
        asks: List of ask entries
        
    Returns:
        True if data is valid, False otherwise
    """
    try:
        # Check that bids and asks are lists
        if not isinstance(bids, list) or not isinstance(asks, list):
            return False
        
        # Check bid format
        for bid in bids:
            if not isinstance(bid, list) or len(bid) != 2:
                return False
            price, qty = bid
            Decimal(str(price))  # Validate price can be converted to Decimal
            Decimal(str(qty))    # Validate quantity can be converted to Decimal
        
        # Check ask format
        for ask in asks:
            if not isinstance(ask, list) or len(ask) != 2:
                return False
            price, qty = ask
            Decimal(str(price))  # Validate price can be converted to Decimal
            Decimal(str(qty))    # Validate quantity can be converted to Decimal
        
        return True
        
    except (ValueError, TypeError, IndexError):
        return False


def convert_to_decimal_order_book(bids: List[List], asks: List[List]) -> tuple:
    """
    Convert order book data to Decimal format.
    
    Args:
        bids: List of bid entries [price, quantity]
        asks: List of ask entries [price, quantity]
        
    Returns:
        Tuple of (converted_bids, converted_asks)
    """
    converted_bids = []
    converted_asks = []
    
    # Convert bids
    for price, qty in bids:
        converted_bids.append([Decimal(str(price)), Decimal(str(qty))])
    
    # Convert asks
    for price, qty in asks:
        converted_asks.append([Decimal(str(price)), Decimal(str(qty))])
    
    return converted_bids, converted_asks
