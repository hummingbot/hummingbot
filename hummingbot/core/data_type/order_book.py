# Simple Python implementation to bypass Cython import issues
from decimal import Decimal
from typing import Dict, List, Optional, Any
from enum import Enum

class OrderBookSide(Enum):
    BID = "bid"
    ASK = "ask"

class OrderBook:
    """
    Simple OrderBook implementation to bypass Cython import issues
    """
    def __init__(self):
        self._bids: List[tuple] = []
        self._asks: List[tuple] = []
        self._last_price: Optional[Decimal] = None
        self._timestamp: float = 0.0
        
    def apply_snapshot(self, bids: List[tuple], asks: List[tuple], timestamp: float):
        """Apply a snapshot of the order book"""
        self._bids = sorted(bids, key=lambda x: x[0], reverse=True)  # Sort by price descending
        self._asks = sorted(asks, key=lambda x: x[0])  # Sort by price ascending
        self._timestamp = timestamp
        
    def apply_diffs(self, bids: List[tuple], asks: List[tuple], timestamp: float):
        """Apply incremental updates to the order book"""
        # Update bids
        for price, amount in bids:
            if amount == 0:
                # Remove the price level
                self._bids = [(p, a) for p, a in self._bids if p != price]
            else:
                # Update or add the price level
                self._bids = [(p, a) for p, a in self._bids if p != price]
                self._bids.append((price, amount))
        
        # Update asks
        for price, amount in asks:
            if amount == 0:
                # Remove the price level
                self._asks = [(p, a) for p, a in self._asks if p != price]
            else:
                # Update or add the price level
                self._asks = [(p, a) for p, a in self._asks if p != price]
                self._asks.append((price, amount))
        
        # Re-sort
        self._bids = sorted(self._bids, key=lambda x: x[0], reverse=True)
        self._asks = sorted(self._asks, key=lambda x: x[0])
        self._timestamp = timestamp
        
    def get_best_bid(self) -> Optional[tuple]:
        """Get the best bid (highest price)"""
        return self._bids[0] if self._bids else None
        
    def get_best_ask(self) -> Optional[tuple]:
        """Get the best ask (lowest price)"""
        return self._asks[0] if self._asks else None
        
    def get_bid_price(self) -> Optional[Decimal]:
        """Get the best bid price"""
        best_bid = self.get_best_bid()
        return Decimal(best_bid[0]) if best_bid else None
        
    def get_ask_price(self) -> Optional[Decimal]:
        """Get the best ask price"""
        best_ask = self.get_best_ask()
        return Decimal(best_ask[0]) if best_ask else None
        
    def get_mid_price(self) -> Optional[Decimal]:
        """Get the mid price between best bid and ask"""
        bid_price = self.get_bid_price()
        ask_price = self.get_ask_price()
        if bid_price and ask_price:
            return (bid_price + ask_price) / 2
        return None
        
    def get_spread(self) -> Optional[Decimal]:
        """Get the spread between best bid and ask"""
        bid_price = self.get_bid_price()
        ask_price = self.get_ask_price()
        if bid_price and ask_price:
            return ask_price - bid_price
        return None
        
    def get_bids(self) -> List[tuple]:
        """Get all bids"""
        return self._bids.copy()
        
    def get_asks(self) -> List[tuple]:
        """Get all asks"""
        return self._asks.copy()
        
    def get_timestamp(self) -> float:
        """Get the timestamp of the last update"""
        return self._timestamp
        
    def is_empty(self) -> bool:
        """Check if the order book is empty"""
        return len(self._bids) == 0 and len(self._asks) == 0
        
    def __repr__(self):
        return f"OrderBook(bids={len(self._bids)}, asks={len(self._asks)}, timestamp={self._timestamp})"
