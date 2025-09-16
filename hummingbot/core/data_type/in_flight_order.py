"""
In-flight order data types for Hummingbot framework.
Minimal implementation to support connector development.
"""

from decimal import Decimal
from enum import Enum
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass
from .common import OrderType, TradeType, OrderState


class OrderUpdate(Enum):
    """Order update types."""
    CREATED = "CREATED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"


@dataclass
class TradeUpdate:
    """Trade update data structure."""
    trade_id: str
    client_order_id: str
    exchange_order_id: str
    trading_pair: str
    fill_timestamp: float
    fill_price: Decimal
    fill_base_amount: Decimal
    fill_quote_amount: Decimal
    fee_amount: Decimal
    fee_asset: str


class InFlightOrder:
    """
    Represents an order that is currently being tracked by the connector.
    """
    
    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: Optional[str],
                 trading_pair: str,
                 order_type: OrderType,
                 trade_type: TradeType,
                 amount: Decimal,
                 price: Decimal,
                 creation_timestamp: float,
                 initial_state: OrderState = OrderState.PENDING_CREATE):
        """
        Initialize an in-flight order.
        
        Args:
            client_order_id: Client-side order identifier
            exchange_order_id: Exchange-side order identifier
            trading_pair: Trading pair for the order
            order_type: Type of order (LIMIT, MARKET, etc.)
            trade_type: Trade type (BUY, SELL)
            amount: Order amount
            price: Order price
            creation_timestamp: When the order was created
            initial_state: Initial order state
        """
        self.client_order_id = client_order_id
        self.exchange_order_id = exchange_order_id
        self.trading_pair = trading_pair
        self.order_type = order_type
        self.trade_type = trade_type
        self.amount = amount
        self.price = price
        self.creation_timestamp = creation_timestamp
        self.current_state = initial_state
        
        self.executed_amount_base = Decimal("0")
        self.executed_amount_quote = Decimal("0")
        self.fee_amount = Decimal("0")
        self.fee_asset = ""
        
        self.last_update_timestamp = creation_timestamp
        self.order_fills: Dict[str, TradeUpdate] = {}
        
    @property
    def is_done(self) -> bool:
        """Check if the order is in a final state."""
        return self.current_state in {
            OrderState.FILLED,
            OrderState.CANCELED,
            OrderState.FAILED
        }
    
    @property
    def is_failure(self) -> bool:
        """Check if the order failed."""
        return self.current_state == OrderState.FAILED
    
    @property
    def is_cancelled(self) -> bool:
        """Check if the order was cancelled."""
        return self.current_state == OrderState.CANCELED
    
    @property
    def is_filled(self) -> bool:
        """Check if the order is completely filled."""
        return self.current_state == OrderState.FILLED
    
    def update_with_trade_update(self, trade_update: TradeUpdate):
        """
        Update the order with a trade update.
        
        Args:
            trade_update: Trade update information
        """
        if trade_update.trade_id not in self.order_fills:
            self.order_fills[trade_update.trade_id] = trade_update
            self.executed_amount_base += trade_update.fill_base_amount
            self.executed_amount_quote += trade_update.fill_quote_amount
            self.fee_amount += trade_update.fee_amount
            self.fee_asset = trade_update.fee_asset
            self.last_update_timestamp = trade_update.fill_timestamp
            
            # Update order state based on fill amount
            if self.executed_amount_base >= self.amount:
                self.current_state = OrderState.FILLED
            elif self.executed_amount_base > Decimal("0"):
                self.current_state = OrderState.PARTIALLY_FILLED
    
    def to_json(self) -> Dict[str, Any]:
        """Convert order to JSON representation."""
        return {
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "trading_pair": self.trading_pair,
            "order_type": self.order_type.value,
            "trade_type": self.trade_type.value,
            "amount": str(self.amount),
            "price": str(self.price),
            "executed_amount_base": str(self.executed_amount_base),
            "executed_amount_quote": str(self.executed_amount_quote),
            "fee_amount": str(self.fee_amount),
            "fee_asset": self.fee_asset,
            "current_state": self.current_state.value,
            "creation_timestamp": self.creation_timestamp,
            "last_update_timestamp": self.last_update_timestamp
        }
