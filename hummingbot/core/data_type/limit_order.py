# Simple Python implementation to bypass Cython import issues
from decimal import Decimal
from typing import Optional, Dict, Any
from enum import Enum

class OrderType(Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    PENDING_CANCEL = "PENDING_CANCEL"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class LimitOrder:
    """
    Simple LimitOrder implementation to bypass Cython import issues
    """
    def __init__(
        self,
        client_order_id: str,
        trading_pair: str,
        is_buy: bool,
        base_currency: str,
        quote_currency: str,
        price: Decimal,
        quantity: Decimal,
        filled_quantity: Decimal = Decimal("0"),
        status: OrderStatus = OrderStatus.NEW,
        creation_timestamp: float = 0.0,
        last_update_timestamp: float = 0.0,
        **kwargs
    ):
        self.client_order_id = client_order_id
        self.trading_pair = trading_pair
        self.is_buy = is_buy
        self.base_currency = base_currency
        self.quote_currency = quote_currency
        self.price = price
        self.quantity = quantity
        self.filled_quantity = filled_quantity
        self.status = status
        self.creation_timestamp = creation_timestamp
        self.last_update_timestamp = last_update_timestamp
        
        # Additional attributes
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    @property
    def is_done(self) -> bool:
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED, OrderStatus.EXPIRED]
    
    @property
    def is_cancelled(self) -> bool:
        return self.status == OrderStatus.CANCELED
    
    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED
    
    @property
    def remaining_quantity(self) -> Decimal:
        return self.quantity - self.filled_quantity
    
    def __repr__(self):
        return (f"LimitOrder(client_order_id='{self.client_order_id}', "
                f"trading_pair='{self.trading_pair}', is_buy={self.is_buy}, "
                f"price={self.price}, quantity={self.quantity}, "
                f"filled_quantity={self.filled_quantity}, status={self.status})")
