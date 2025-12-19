"""
Python wrapper for LimitOrder - provides compatibility with tests.

This module provides a Python interface to the LimitOrder class
for testing and compatibility purposes.
"""

from decimal import Decimal
from typing import Optional

from hummingbot.core.data_type.common import OrderType, PositionAction
from hummingbot.core.event.events import LimitOrderStatus

# Try to import from Cython module, fall back to Python implementation
try:
    from hummingbot.core.data_type.limit_order import LimitOrder as CythonLimitOrder
    _has_cython = True
except ImportError:
    _has_cython = False


class LimitOrder:
    """
    Python implementation of LimitOrder for testing and compatibility.
    
    This class stores order information and is used throughout Hummingbot
    for order management and tracking.
    """
    
    def __init__(self,
                 client_order_id: str,
                 trading_pair: str,
                 is_buy: bool,
                 base_currency: str,
                 quote_currency: str,
                 price: Decimal,
                 quantity: Decimal,
                 filled_quantity: Decimal = Decimal("0"),
                 creation_timestamp: int = 0,
                 status: LimitOrderStatus = LimitOrderStatus.UNKNOWN,
                 position: PositionAction = PositionAction.NIL):
        """
        Initialize a LimitOrder.
        
        Args:
            client_order_id: Client order ID
            trading_pair: Trading pair
            is_buy: True for buy orders, False for sell orders
            base_currency: Base currency
            quote_currency: Quote currency
            price: Order price
            quantity: Order quantity
            filled_quantity: Filled quantity
            creation_timestamp: Creation timestamp
            status: Order status
            position: Position action
        """
        self._client_order_id = client_order_id
        self._trading_pair = trading_pair
        self._is_buy = is_buy
        self._base_currency = base_currency
        self._quote_currency = quote_currency
        self._price = price
        self._quantity = quantity
        self._filled_quantity = filled_quantity
        self._creation_timestamp = creation_timestamp
        self._status = status
        self._position = position
    
    @property
    def client_order_id(self) -> str:
        """Get client order ID."""
        return self._client_order_id
    
    @property
    def trading_pair(self) -> str:
        """Get trading pair."""
        return self._trading_pair
    
    @property
    def is_buy(self) -> bool:
        """Check if buy order."""
        return self._is_buy
    
    @property
    def base_currency(self) -> str:
        """Get base currency."""
        return self._base_currency
    
    @property
    def quote_currency(self) -> str:
        """Get quote currency."""
        return self._quote_currency
    
    @property
    def price(self) -> Decimal:
        """Get order price."""
        return self._price
    
    @property
    def quantity(self) -> Decimal:
        """Get order quantity."""
        return self._quantity
    
    @property
    def filled_quantity(self) -> Decimal:
        """Get filled quantity."""
        return self._filled_quantity
    
    @property
    def creation_timestamp(self) -> int:
        """Get creation timestamp."""
        return self._creation_timestamp
    
    @property
    def status(self) -> LimitOrderStatus:
        """Get order status."""
        return self._status
    
    @property
    def position(self) -> PositionAction:
        """Get position action."""
        return self._position
    
    def order_type(self) -> OrderType:
        """Get order type."""
        return OrderType.LIMIT
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"LimitOrder('{self.client_order_id}', '{self.trading_pair}', "
            f"{self.is_buy}, '{self.base_currency}', '{self.quote_currency}', "
            f"{self.price}, {self.quantity}, {self.filled_quantity}, "
            f"{self.creation_timestamp})"
        )
