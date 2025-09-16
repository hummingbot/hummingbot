"""
Trading rule data types for Hummingbot connectors.
Minimal implementation to support connector development.
"""

from decimal import Decimal
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class TradingRule:
    """
    Trading rule for a specific trading pair on an exchange.
    Contains information about minimum/maximum order sizes, price increments, etc.
    """
    
    trading_pair: str
    min_order_size: Decimal
    max_order_size: Decimal
    min_price_increment: Decimal
    min_base_amount_increment: Decimal
    min_quote_amount_increment: Decimal
    min_notional_size: Decimal
    max_price: Optional[Decimal] = None
    min_price: Optional[Decimal] = None
    supports_limit_orders: bool = True
    supports_market_orders: bool = True
    buy_order_collateral_token: Optional[str] = None
    sell_order_collateral_token: Optional[str] = None
    
    def __post_init__(self):
        """Post-initialization validation."""
        # Ensure all Decimal fields are actually Decimal objects
        decimal_fields = [
            'min_order_size', 'max_order_size', 'min_price_increment',
            'min_base_amount_increment', 'min_quote_amount_increment',
            'min_notional_size'
        ]
        
        for field in decimal_fields:
            value = getattr(self, field)
            if not isinstance(value, Decimal):
                setattr(self, field, Decimal(str(value)))
        
        # Handle optional Decimal fields
        optional_decimal_fields = ['max_price', 'min_price']
        for field in optional_decimal_fields:
            value = getattr(self, field)
            if value is not None and not isinstance(value, Decimal):
                setattr(self, field, Decimal(str(value)))
    
    @classmethod
    def from_exchange_info(cls, 
                          trading_pair: str, 
                          exchange_info: Dict[str, Any]) -> 'TradingRule':
        """
        Create a TradingRule from exchange information.
        
        Args:
            trading_pair: Trading pair symbol
            exchange_info: Exchange information dictionary
            
        Returns:
            TradingRule instance
        """
        # Default values
        min_order_size = Decimal("0.001")
        max_order_size = Decimal("1000000")
        min_price_increment = Decimal("0.00000001")
        min_base_amount_increment = Decimal("0.00000001")
        min_quote_amount_increment = Decimal("0.00000001")
        min_notional_size = Decimal("0.001")
        
        # Extract values from exchange info if available
        if 'filters' in exchange_info:
            for filter_info in exchange_info['filters']:
                filter_type = filter_info.get('filterType')
                
                if filter_type == 'LOT_SIZE':
                    min_order_size = Decimal(str(filter_info.get('minQty', min_order_size)))
                    max_order_size = Decimal(str(filter_info.get('maxQty', max_order_size)))
                    min_base_amount_increment = Decimal(str(filter_info.get('stepSize', min_base_amount_increment)))
                
                elif filter_type == 'PRICE_FILTER':
                    min_price_increment = Decimal(str(filter_info.get('tickSize', min_price_increment)))
                
                elif filter_type == 'MIN_NOTIONAL':
                    min_notional_size = Decimal(str(filter_info.get('minNotional', min_notional_size)))
        
        return cls(
            trading_pair=trading_pair,
            min_order_size=min_order_size,
            max_order_size=max_order_size,
            min_price_increment=min_price_increment,
            min_base_amount_increment=min_base_amount_increment,
            min_quote_amount_increment=min_quote_amount_increment,
            min_notional_size=min_notional_size
        )
    
    def validate_order_size(self, order_size: Decimal) -> bool:
        """
        Validate if an order size meets the trading rule requirements.
        
        Args:
            order_size: Order size to validate
            
        Returns:
            True if valid, False otherwise
        """
        return (self.min_order_size <= order_size <= self.max_order_size and
                order_size % self.min_base_amount_increment == 0)
    
    def validate_price(self, price: Decimal) -> bool:
        """
        Validate if a price meets the trading rule requirements.
        
        Args:
            price: Price to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check price increment
        if price % self.min_price_increment != 0:
            return False
        
        # Check min/max price if specified
        if self.min_price is not None and price < self.min_price:
            return False
        
        if self.max_price is not None and price > self.max_price:
            return False
        
        return True
    
    def validate_notional_size(self, price: Decimal, quantity: Decimal) -> bool:
        """
        Validate if the notional size (price * quantity) meets requirements.
        
        Args:
            price: Order price
            quantity: Order quantity
            
        Returns:
            True if valid, False otherwise
        """
        notional_size = price * quantity
        return notional_size >= self.min_notional_size
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert trading rule to dictionary representation.
        
        Returns:
            Dictionary representation of the trading rule
        """
        return {
            'trading_pair': self.trading_pair,
            'min_order_size': str(self.min_order_size),
            'max_order_size': str(self.max_order_size),
            'min_price_increment': str(self.min_price_increment),
            'min_base_amount_increment': str(self.min_base_amount_increment),
            'min_quote_amount_increment': str(self.min_quote_amount_increment),
            'min_notional_size': str(self.min_notional_size),
            'max_price': str(self.max_price) if self.max_price else None,
            'min_price': str(self.min_price) if self.min_price else None,
            'supports_limit_orders': self.supports_limit_orders,
            'supports_market_orders': self.supports_market_orders,
            'buy_order_collateral_token': self.buy_order_collateral_token,
            'sell_order_collateral_token': self.sell_order_collateral_token
        }
    
    def __str__(self) -> str:
        """String representation of the trading rule."""
        return (f"TradingRule({self.trading_pair}: "
                f"size={self.min_order_size}-{self.max_order_size}, "
                f"price_inc={self.min_price_increment}, "
                f"min_notional={self.min_notional_size})")
