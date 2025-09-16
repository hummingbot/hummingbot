"""
Order book tracker data source for Hummingbot framework.
Minimal implementation to support connector development.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncIterable
from decimal import Decimal

from .order_book import OrderBook
from .common import TradingPair


class OrderBookTrackerDataSource(ABC):
    """
    Abstract base class for order book tracker data sources.
    Handles fetching and streaming order book data from exchanges.
    """
    
    def __init__(self, trading_pairs: List[str]):
        """
        Initialize the order book tracker data source.
        
        Args:
            trading_pairs: List of trading pairs to track
        """
        self._trading_pairs = trading_pairs
        self._logger = logging.getLogger(__name__)
        self._order_books: Dict[str, OrderBook] = {}
        
        # Initialize order books
        for trading_pair in trading_pairs:
            self._order_books[trading_pair] = OrderBook(trading_pair)
    
    @property
    def trading_pairs(self) -> List[str]:
        """Get list of trading pairs being tracked."""
        return self._trading_pairs.copy()
    
    @property
    def order_books(self) -> Dict[str, OrderBook]:
        """Get dictionary of order books."""
        return self._order_books.copy()
    
    def get_order_book(self, trading_pair: str) -> Optional[OrderBook]:
        """
        Get order book for a specific trading pair.
        
        Args:
            trading_pair: Trading pair to get order book for
            
        Returns:
            OrderBook instance or None if not found
        """
        return self._order_books.get(trading_pair)
    
    @abstractmethod
    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, Decimal]:
        """
        Get last traded prices for trading pairs.
        
        Args:
            trading_pairs: List of trading pairs
            
        Returns:
            Dictionary mapping trading pairs to last traded prices
        """
        pass
    
    @abstractmethod
    async def get_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Get order book snapshot for a trading pair.
        
        Args:
            trading_pair: Trading pair to get snapshot for
            
        Returns:
            Order book snapshot data
        """
        pass
    
    @abstractmethod
    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop, 
                                        output: asyncio.Queue) -> None:
        """
        Listen for order book difference messages.
        
        Args:
            ev_loop: Event loop
            output: Output queue for order book diff messages
        """
        pass
    
    @abstractmethod
    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop,
                                            output: asyncio.Queue) -> None:
        """
        Listen for order book snapshot messages.
        
        Args:
            ev_loop: Event loop
            output: Output queue for order book snapshot messages
        """
        pass
    
    @abstractmethod
    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop,
                              output: asyncio.Queue) -> None:
        """
        Listen for trade messages.
        
        Args:
            ev_loop: Event loop
            output: Output queue for trade messages
        """
        pass
    
    async def start(self) -> None:
        """Start the data source."""
        self._logger.info(f"Starting order book tracker data source for {len(self._trading_pairs)} pairs")
    
    async def stop(self) -> None:
        """Stop the data source."""
        self._logger.info("Stopping order book tracker data source")
    
    def update_order_book(self, trading_pair: str, bids: List[List], asks: List[List], 
                         update_id: int) -> None:
        """
        Update order book with new data.
        
        Args:
            trading_pair: Trading pair to update
            bids: List of bid entries [price, amount]
            asks: List of ask entries [price, amount]
            update_id: Update ID for tracking
        """
        if trading_pair not in self._order_books:
            return
        
        order_book = self._order_books[trading_pair]
        
        # Update bids
        for bid in bids:
            price = Decimal(str(bid[0]))
            amount = Decimal(str(bid[1]))
            order_book.update_bid(price, amount, update_id)
        
        # Update asks
        for ask in asks:
            price = Decimal(str(ask[0]))
            amount = Decimal(str(ask[1]))
            order_book.update_ask(price, amount, update_id)


class OrderBookTrackerDataSourceError(Exception):
    """Exception raised by order book tracker data source."""
    pass


class MockOrderBookTrackerDataSource(OrderBookTrackerDataSource):
    """
    Mock implementation of order book tracker data source for testing.
    """
    
    def __init__(self, trading_pairs: List[str]):
        """Initialize mock data source."""
        super().__init__(trading_pairs)
        self._mock_prices: Dict[str, Decimal] = {}
        
        # Initialize with mock prices
        for trading_pair in trading_pairs:
            self._mock_prices[trading_pair] = Decimal("100.0")
    
    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, Decimal]:
        """Get mock last traded prices."""
        return {tp: self._mock_prices.get(tp, Decimal("100.0")) for tp in trading_pairs}
    
    async def get_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """Get mock order book snapshot."""
        return {
            "bids": [["99.0", "1.0"], ["98.0", "2.0"]],
            "asks": [["101.0", "1.0"], ["102.0", "2.0"]],
            "lastUpdateId": 12345
        }
    
    async def listen_for_order_book_diffs(self, ev_loop: asyncio.AbstractEventLoop,
                                        output: asyncio.Queue) -> None:
        """Mock order book diff listener."""
        # Mock implementation - just wait
        await asyncio.sleep(1)
    
    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop,
                                            output: asyncio.Queue) -> None:
        """Mock order book snapshot listener."""
        # Mock implementation - just wait
        await asyncio.sleep(1)
    
    async def listen_for_trades(self, ev_loop: asyncio.AbstractEventLoop,
                              output: asyncio.Queue) -> None:
        """Mock trade listener."""
        # Mock implementation - just wait
        await asyncio.sleep(1)
