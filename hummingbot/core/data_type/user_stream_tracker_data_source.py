"""
User stream tracker data source for Hummingbot framework.
Minimal implementation to support connector development.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncIterable
from decimal import Decimal


class UserStreamTrackerDataSource(ABC):
    """
    Abstract base class for user stream tracker data sources.
    Handles fetching and streaming user-specific data from exchanges (orders, balances, trades).
    """
    
    def __init__(self):
        """Initialize the user stream tracker data source."""
        self._logger = logging.getLogger(__name__)
        self._auth = None
        self._trading_pairs: List[str] = []
        self._last_recv_time: float = 0
    
    @property
    def last_recv_time(self) -> float:
        """Get the last received message timestamp."""
        return self._last_recv_time
    
    @property
    def trading_pairs(self) -> List[str]:
        """Get list of trading pairs being tracked."""
        return self._trading_pairs.copy()
    
    def configure_auth(self, auth) -> None:
        """
        Configure authentication for the data source.
        
        Args:
            auth: Authentication handler
        """
        self._auth = auth
    
    def configure_trading_pairs(self, trading_pairs: List[str]) -> None:
        """
        Configure trading pairs to track.
        
        Args:
            trading_pairs: List of trading pairs to track
        """
        self._trading_pairs = trading_pairs.copy()
    
    @abstractmethod
    async def listen_for_user_stream(self, ev_loop: asyncio.AbstractEventLoop,
                                   output: asyncio.Queue) -> None:
        """
        Listen for user stream messages.
        
        Args:
            ev_loop: Event loop
            output: Output queue for user stream messages
        """
        pass
    
    @abstractmethod
    async def get_account_balances(self) -> Dict[str, Decimal]:
        """
        Get account balances.
        
        Returns:
            Dictionary mapping asset symbols to balances
        """
        pass
    
    @abstractmethod
    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """
        Get open orders.
        
        Returns:
            List of open order dictionaries
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get order status.
        
        Args:
            order_id: Order ID to check
            
        Returns:
            Order status dictionary
        """
        pass
    
    async def start(self) -> None:
        """Start the user stream data source."""
        self._logger.info("Starting user stream tracker data source")
    
    async def stop(self) -> None:
        """Stop the user stream data source."""
        self._logger.info("Stopping user stream tracker data source")
    
    def _update_last_recv_time(self) -> None:
        """Update the last received message timestamp."""
        import time
        self._last_recv_time = time.time()


class UserStreamTrackerDataSourceError(Exception):
    """Exception raised by user stream tracker data source."""
    pass


class MockUserStreamTrackerDataSource(UserStreamTrackerDataSource):
    """
    Mock implementation of user stream tracker data source for testing.
    """
    
    def __init__(self):
        """Initialize mock user stream data source."""
        super().__init__()
        self._mock_balances: Dict[str, Decimal] = {
            "BTC": Decimal("1.0"),
            "ETH": Decimal("10.0"),
            "PHP": Decimal("50000.0")
        }
        self._mock_orders: List[Dict[str, Any]] = []
    
    async def listen_for_user_stream(self, ev_loop: asyncio.AbstractEventLoop,
                                   output: asyncio.Queue) -> None:
        """Mock user stream listener."""
        try:
            while True:
                # Simulate receiving user stream messages
                await asyncio.sleep(1)
                
                # Mock balance update message
                balance_update = {
                    "type": "balance_update",
                    "data": {
                        "asset": "BTC",
                        "balance": str(self._mock_balances.get("BTC", Decimal("0")))
                    }
                }
                
                await output.put(balance_update)
                self._update_last_recv_time()
                
        except asyncio.CancelledError:
            self._logger.info("User stream listener cancelled")
        except Exception as e:
            self._logger.error(f"Error in user stream listener: {e}")
    
    async def get_account_balances(self) -> Dict[str, Decimal]:
        """Get mock account balances."""
        return self._mock_balances.copy()
    
    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get mock open orders."""
        return self._mock_orders.copy()
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get mock order status."""
        return {
            "orderId": order_id,
            "status": "FILLED",
            "executedQty": "1.0",
            "cummulativeQuoteQty": "50000.0"
        }
    
    def add_mock_order(self, order: Dict[str, Any]) -> None:
        """Add a mock order for testing."""
        self._mock_orders.append(order)
    
    def update_mock_balance(self, asset: str, balance: Decimal) -> None:
        """Update mock balance for testing."""
        self._mock_balances[asset] = balance


class UserStreamMessage:
    """
    Represents a user stream message.
    """
    
    def __init__(self, message_type: str, data: Dict[str, Any], timestamp: float):
        """
        Initialize user stream message.
        
        Args:
            message_type: Type of message (balance_update, order_update, trade_update)
            data: Message data
            timestamp: Message timestamp
        """
        self.message_type = message_type
        self.data = data
        self.timestamp = timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "type": self.message_type,
            "data": self.data,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, message_dict: Dict[str, Any]) -> 'UserStreamMessage':
        """Create message from dictionary."""
        return cls(
            message_type=message_dict.get("type", "unknown"),
            data=message_dict.get("data", {}),
            timestamp=message_dict.get("timestamp", 0.0)
        )
    
    def __str__(self) -> str:
        """String representation of the message."""
        return f"UserStreamMessage({self.message_type}: {self.data})"


# Message type constants
USER_STREAM_MESSAGE_TYPES = {
    "BALANCE_UPDATE": "balance_update",
    "ORDER_UPDATE": "order_update", 
    "TRADE_UPDATE": "trade_update",
    "ACCOUNT_UPDATE": "account_update"
}
