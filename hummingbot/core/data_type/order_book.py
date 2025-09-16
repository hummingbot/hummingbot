"""
Order book data types for Hummingbot framework.
Minimal implementation to support connector development.
"""

from decimal import Decimal
from typing import Dict, List, Optional
from dataclasses import dataclass
from .common import OrderBookEntry


@dataclass
class OrderBookRow:
    """Order book row data structure."""
    price: Decimal
    amount: Decimal
    update_id: int


class OrderBook:
    """
    Order book data structure.
    """
    
    def __init__(self, trading_pair: str):
        """
        Initialize order book.
        
        Args:
            trading_pair: The trading pair for this order book
        """
        self.trading_pair = trading_pair
        self._bids: Dict[Decimal, OrderBookRow] = {}
        self._asks: Dict[Decimal, OrderBookRow] = {}
        self._last_update_id: int = 0
    
    @property
    def bids(self) -> List[OrderBookRow]:
        """Get sorted bids (highest price first)."""
        return sorted(self._bids.values(), key=lambda x: x.price, reverse=True)
    
    @property
    def asks(self) -> List[OrderBookRow]:
        """Get sorted asks (lowest price first)."""
        return sorted(self._asks.values(), key=lambda x: x.price)
    
    def get_best_bid(self) -> Optional[OrderBookRow]:
        """Get the best bid price."""
        bids = self.bids
        return bids[0] if bids else None
    
    def get_best_ask(self) -> Optional[OrderBookRow]:
        """Get the best ask price."""
        asks = self.asks
        return asks[0] if asks else None
    
    def update_bid(self, price: Decimal, amount: Decimal, update_id: int):
        """Update a bid entry."""
        if amount == 0:
            self._bids.pop(price, None)
        else:
            self._bids[price] = OrderBookRow(price, amount, update_id)
        self._last_update_id = max(self._last_update_id, update_id)
    
    def update_ask(self, price: Decimal, amount: Decimal, update_id: int):
        """Update an ask entry."""
        if amount == 0:
            self._asks.pop(price, None)
        else:
            self._asks[price] = OrderBookRow(price, amount, update_id)
        self._last_update_id = max(self._last_update_id, update_id)
