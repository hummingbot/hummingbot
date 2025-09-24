"""
Order Book Tracker for Coins.xyz Exchange Connector

This module handles order book tracking and management for the Coins.xyz exchange,
providing real-time order book updates and maintaining order book state.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set
from decimal import Decimal

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
# from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.utils.async_utils import safe_ensure_future


class CoinsxyzOrderBookTracker:
    """
    Order book tracker for Coins.xyz exchange.
    
    Manages real-time order book updates and maintains order book state
    for all tracked trading pairs.
    """
    
    def __init__(self, trading_pairs: Optional[List[str]] = None):
        """
        Initialize the order book tracker.
        
        :param trading_pairs: List of trading pairs to track
        """
        # super().__init__()
        self._logger = logging.getLogger(__name__)
        self._trading_pairs: Set[str] = set(trading_pairs or [])
        self._order_books: Dict[str, OrderBook] = {}
        self._tracking_tasks: Dict[str, asyncio.Task] = {}
        self._started = False
    
    @property
    def exchange_name(self) -> str:
        """Get the exchange name."""
        return CONSTANTS.EXCHANGE_NAME
    
    async def start(self):
        """Start the order book tracker."""
        if self._started:
            return
        
        self._logger.info("Starting Coins.xyz order book tracker")
        
        # Initialize order books for all trading pairs
        for trading_pair in self._trading_pairs:
            await self._initialize_order_book(trading_pair)
        
        # Start tracking tasks
        for trading_pair in self._trading_pairs:
            task = safe_ensure_future(self._track_order_book(trading_pair))
            self._tracking_tasks[trading_pair] = task
        
        self._started = True
        self._logger.info(f"Order book tracker started for {len(self._trading_pairs)} pairs")
    
    async def stop(self):
        """Stop the order book tracker."""
        if not self._started:
            return
        
        self._logger.info("Stopping Coins.xyz order book tracker")
        
        # Cancel all tracking tasks
        for task in self._tracking_tasks.values():
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._tracking_tasks:
            await asyncio.gather(*self._tracking_tasks.values(), return_exceptions=True)
        
        self._tracking_tasks.clear()
        self._started = False
        self._logger.info("Order book tracker stopped")
    
    def add_trading_pair(self, trading_pair: str):
        """
        Add a trading pair to track.
        
        :param trading_pair: Trading pair to add
        """
        if trading_pair not in self._trading_pairs:
            self._trading_pairs.add(trading_pair)
            
            if self._started:
                # Start tracking immediately if tracker is already running
                task = safe_ensure_future(self._track_order_book(trading_pair))
                self._tracking_tasks[trading_pair] = task
                self._logger.info(f"Added tracking for {trading_pair}")
    
    def remove_trading_pair(self, trading_pair: str):
        """
        Remove a trading pair from tracking.
        
        :param trading_pair: Trading pair to remove
        """
        if trading_pair in self._trading_pairs:
            self._trading_pairs.discard(trading_pair)
            
            # Cancel tracking task if running
            if trading_pair in self._tracking_tasks:
                task = self._tracking_tasks.pop(trading_pair)
                if not task.done():
                    task.cancel()
            
            # Remove order book
            if trading_pair in self._order_books:
                del self._order_books[trading_pair]
            
            self._logger.info(f"Removed tracking for {trading_pair}")
    
    def get_order_book(self, trading_pair: str) -> Optional[OrderBook]:
        """
        Get order book for a trading pair.
        
        :param trading_pair: Trading pair
        :return: Order book or None if not found
        """
        return self._order_books.get(trading_pair)
    
    async def _initialize_order_book(self, trading_pair: str):
        """
        Initialize order book for a trading pair.
        
        :param trading_pair: Trading pair to initialize
        """
        try:
            # Create new order book
            order_book = OrderBook()
            self._order_books[trading_pair] = order_book
            
            self._logger.info(f"Initialized order book for {trading_pair}")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize order book for {trading_pair}: {e}")
    
    async def _track_order_book(self, trading_pair: str):
        """
        Track order book updates for a trading pair.
        
        :param trading_pair: Trading pair to track
        """
        try:
            self._logger.info(f"Starting order book tracking for {trading_pair}")
            
            while self._started:
                try:
                    # This would normally connect to WebSocket and process messages
                    # For now, we'll just maintain the structure
                    await asyncio.sleep(1.0)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self._logger.error(f"Error tracking {trading_pair}: {e}")
                    await asyncio.sleep(5.0)  # Wait before retrying
                    
        except asyncio.CancelledError:
            self._logger.info(f"Order book tracking cancelled for {trading_pair}")
        except Exception as e:
            self._logger.error(f"Fatal error tracking {trading_pair}: {e}")
    
    def _process_order_book_message(self, trading_pair: str, message: OrderBookMessage):
        """
        Process an order book message.
        
        :param trading_pair: Trading pair
        :param message: Order book message to process
        """
        try:
            order_book = self._order_books.get(trading_pair)
            if not order_book:
                return
            
            if message.type == OrderBookMessageType.SNAPSHOT:
                order_book.apply_snapshot(message.bids, message.asks, message.update_id)
            elif message.type == OrderBookMessageType.DIFF:
                order_book.apply_diffs(message.bids, message.asks, message.update_id)
            
        except Exception as e:
            self._logger.error(f"Error processing order book message for {trading_pair}: {e}")
    
    @property
    def ready(self) -> bool:
        """Check if tracker is ready."""
        return self._started and len(self._order_books) > 0
    
    @property
    def trading_pairs(self) -> List[str]:
        """Get list of tracked trading pairs."""
        return list(self._trading_pairs)
