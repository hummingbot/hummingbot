"""
Trading Rule Module - Python implementation for compatibility.

This module provides the TradingRule class used throughout Hummingbot
for managing trading constraints and rules.
"""

from decimal import Decimal
from typing import Optional


class TradingRule:
    """
    Trading rule for a specific trading pair.
    
    Contains constraints and rules for trading including:
    - Minimum and maximum order sizes
    - Price and quantity increments
    - Minimum notional values
    - Order type support
    """
    
    def __init__(self,
                 trading_pair: str,
                 min_order_size: Decimal = Decimal("0"),
                 max_order_size: Decimal = Decimal("1000000"),
                 min_price_increment: Decimal = Decimal("0.00000001"),
                 min_base_amount_increment: Decimal = Decimal("0.00000001"),
                 min_quote_amount_increment: Decimal = Decimal("0.00000001"),
                 min_notional_size: Decimal = Decimal("0"),
                 min_order_value: Decimal = Decimal("0"),
                 max_price_significant_digits: Decimal = Decimal("8"),
                 supports_limit_orders: bool = True,
                 supports_market_orders: bool = True,
                 buy_order_collateral_token: Optional[str] = None,
                 sell_order_collateral_token: Optional[str] = None):
        """
        Initialize a TradingRule.
        
        Args:
            trading_pair: Trading pair (e.g., "BTC-USDT")
            min_order_size: Minimum order size
            max_order_size: Maximum order size
            min_price_increment: Minimum price increment
            min_base_amount_increment: Minimum base amount increment
            min_quote_amount_increment: Minimum quote amount increment
            min_notional_size: Minimum notional size
            min_order_value: Minimum order value
            max_price_significant_digits: Maximum price significant digits
            supports_limit_orders: Whether limit orders are supported
            supports_market_orders: Whether market orders are supported
            buy_order_collateral_token: Buy order collateral token
            sell_order_collateral_token: Sell order collateral token
        """
        self.trading_pair = trading_pair
        self.min_order_size = min_order_size
        self.max_order_size = max_order_size
        self.min_price_increment = min_price_increment
        self.min_base_amount_increment = min_base_amount_increment
        self.min_quote_amount_increment = min_quote_amount_increment
        self.min_notional_size = min_notional_size
        self.min_order_value = min_order_value
        self.max_price_significant_digits = max_price_significant_digits
        self.supports_limit_orders = supports_limit_orders
        self.supports_market_orders = supports_market_orders
        
        # Determine collateral tokens
        if trading_pair and "-" in trading_pair:
            base_token, quote_token = trading_pair.split("-")
            self.buy_order_collateral_token = buy_order_collateral_token or quote_token
            self.sell_order_collateral_token = sell_order_collateral_token or quote_token
        else:
            self.buy_order_collateral_token = buy_order_collateral_token
            self.sell_order_collateral_token = sell_order_collateral_token
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"TradingRule(trading_pair='{self.trading_pair}', "
            f"min_order_size={self.min_order_size}, "
            f"max_order_size={self.max_order_size}, "
            f"min_price_increment={self.min_price_increment}, "
            f"min_base_amount_increment={self.min_base_amount_increment}, "
            f"min_quote_amount_increment={self.min_quote_amount_increment}, "
            f"min_notional_size={self.min_notional_size}, "
            f"min_order_value={self.min_order_value}, "
            f"max_price_significant_digits={self.max_price_significant_digits}, "
            f"supports_limit_orders={self.supports_limit_orders}, "
            f"supports_market_orders={self.supports_market_orders}, "
            f"buy_order_collateral_token={self.buy_order_collateral_token}, "
            f"sell_order_collateral_token={self.sell_order_collateral_token})"
        )
