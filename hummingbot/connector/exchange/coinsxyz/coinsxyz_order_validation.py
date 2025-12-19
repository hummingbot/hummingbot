"""
Order Validation Utilities for Coins.xyz Exchange.

This module provides comprehensive order validation including:
- Pre-submission order validation
- Trading rules enforcement
- Balance and risk checks
- Order parameter validation
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.logger import HummingbotLogger


@dataclass
class TradingRule:
    """Trading rule for a specific trading pair."""
    trading_pair: str
    min_order_size: Decimal
    max_order_size: Decimal
    min_price_increment: Decimal
    min_base_amount_increment: Decimal
    min_quote_amount_increment: Decimal
    min_notional_size: Decimal
    max_price_significant_digits: int
    max_base_amount_significant_digits: int


@dataclass
class OrderValidationResult:
    """Order validation result."""
    is_valid: bool
    error_message: Optional[str] = None
    warnings: List[str] = None
    adjusted_amount: Optional[Decimal] = None
    adjusted_price: Optional[Decimal] = None


class CoinsxyzOrderValidation:
    """
    Order validation utilities for Coins.xyz exchange.

    Provides comprehensive validation for:
    - Order parameter validation
    - Trading rules enforcement
    - Balance and risk checks
    - Price and amount precision
    - Minimum order size requirements
    """

    def __init__(self):
        """Initialize order validation."""
        self._logger = None
        self._trading_rules: Dict[str, TradingRule] = {}

        # Default trading rules (will be updated from exchange info)
        self._default_rules = TradingRule(
            trading_pair="DEFAULT",
            min_order_size=Decimal("0.001"),
            max_order_size=Decimal("1000000"),
            min_price_increment=Decimal("0.00000001"),
            min_base_amount_increment=Decimal("0.00000001"),
            min_quote_amount_increment=Decimal("0.00000001"),
            min_notional_size=Decimal("10.0"),
            max_price_significant_digits=8,
            max_base_amount_significant_digits=8
        )

    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger

    def validate_order_parameters(self,
                                  trading_pair: str,
                                  order_type: OrderType,
                                  trade_type: TradeType,
                                  amount: Decimal,
                                  price: Optional[Decimal] = None,
                                  available_balance: Optional[Decimal] = None) -> OrderValidationResult:
        """
        Validate order parameters comprehensively.

        Args:
            trading_pair: Trading pair (e.g., "BTC-USDT")
            order_type: Order type (LIMIT, MARKET)
            trade_type: Trade type (BUY, SELL)
            amount: Order amount
            price: Order price (required for LIMIT orders)
            available_balance: Available balance for the order

        Returns:
            OrderValidationResult with validation outcome
        """
        try:
            warnings = []

            # Get trading rules
            trading_rule = self._get_trading_rule(trading_pair)

            # Basic parameter validation
            basic_validation = self._validate_basic_parameters(
                order_type, trade_type, amount, price
            )
            if not basic_validation.is_valid:
                return basic_validation

            # Trading rules validation
            rules_validation = self._validate_trading_rules(
                trading_rule, order_type, amount, price
            )
            if not rules_validation.is_valid:
                return rules_validation

            warnings.extend(rules_validation.warnings or [])

            # Balance validation
            if available_balance is not None:
                balance_validation = self._validate_balance(
                    trade_type, amount, price, available_balance
                )
                if not balance_validation.is_valid:
                    return balance_validation

                warnings.extend(balance_validation.warnings or [])

            # Precision validation
            precision_validation = self._validate_precision(
                trading_rule, amount, price
            )
            if not precision_validation.is_valid:
                return precision_validation

            warnings.extend(precision_validation.warnings or [])

            return OrderValidationResult(
                is_valid=True,
                warnings=warnings if warnings else None,
                adjusted_amount=precision_validation.adjusted_amount,
                adjusted_price=precision_validation.adjusted_price
            )

        except Exception as e:
            self.logger().error(f"Error validating order parameters: {e}")
            return OrderValidationResult(
                is_valid=False,
                error_message=f"Validation error: {e}"
            )

    def _validate_basic_parameters(self,
                                   order_type: OrderType,
                                   trade_type: TradeType,
                                   amount: Decimal,
                                   price: Optional[Decimal]) -> OrderValidationResult:
        """
        Validate basic order parameters.

        Args:
            order_type: Order type
            trade_type: Trade type
            amount: Order amount
            price: Order price

        Returns:
            OrderValidationResult
        """
        # Check amount
        if amount <= 0:
            return OrderValidationResult(
                is_valid=False,
                error_message="Order amount must be positive"
            )

        # Check price for limit orders
        if order_type == OrderType.LIMIT:
            if price is None:
                return OrderValidationResult(
                    is_valid=False,
                    error_message="Price is required for LIMIT orders"
                )

            if price <= 0:
                return OrderValidationResult(
                    is_valid=False,
                    error_message="Order price must be positive"
                )

        # Check for NaN or infinite values
        if not amount.is_finite():
            return OrderValidationResult(
                is_valid=False,
                error_message="Order amount must be a finite number"
            )

        if price is not None and not price.is_finite():
            return OrderValidationResult(
                is_valid=False,
                error_message="Order price must be a finite number"
            )

        return OrderValidationResult(is_valid=True)

    def _validate_trading_rules(self,
                                trading_rule: TradingRule,
                                order_type: OrderType,
                                amount: Decimal,
                                price: Optional[Decimal]) -> OrderValidationResult:
        """
        Validate order against trading rules.

        Args:
            trading_rule: Trading rule for the pair
            order_type: Order type
            amount: Order amount
            price: Order price

        Returns:
            OrderValidationResult
        """
        warnings = []

        # Check minimum order size
        if amount < trading_rule.min_order_size:
            return OrderValidationResult(
                is_valid=False,
                error_message=f"Order amount {amount} is below minimum size {trading_rule.min_order_size}"
            )

        # Check maximum order size
        if amount > trading_rule.max_order_size:
            return OrderValidationResult(
                is_valid=False,
                error_message=f"Order amount {amount} exceeds maximum size {trading_rule.max_order_size}"
            )

        # Check minimum notional value for limit orders
        if order_type == OrderType.LIMIT and price is not None:
            notional_value = amount * price
            if notional_value < trading_rule.min_notional_size:
                return OrderValidationResult(
                    is_valid=False,
                    error_message=f"Order notional value {notional_value} is below minimum {trading_rule.min_notional_size}"
                )

        return OrderValidationResult(is_valid=True, warnings=warnings)

    def _validate_balance(self,
                          trade_type: TradeType,
                          amount: Decimal,
                          price: Optional[Decimal],
                          available_balance: Decimal) -> OrderValidationResult:
        """
        Validate order against available balance.

        Args:
            trade_type: Trade type (BUY/SELL)
            amount: Order amount
            price: Order price
            available_balance: Available balance

        Returns:
            OrderValidationResult
        """
        warnings = []

        if trade_type == TradeType.BUY:
            # For buy orders, check quote currency balance
            if price is not None:
                required_balance = amount * price
                if required_balance > available_balance:
                    return OrderValidationResult(
                        is_valid=False,
                        error_message=f"Insufficient balance: required {required_balance}, available {available_balance}"
                    )

                # Warn if using most of available balance
                if required_balance > available_balance * Decimal("0.95"):
                    warnings.append("Order uses more than 95% of available balance")

        else:  # SELL
            # For sell orders, check base currency balance
            if amount > available_balance:
                return OrderValidationResult(
                    is_valid=False,
                    error_message=f"Insufficient balance: required {amount}, available {available_balance}"
                )

            # Warn if selling most of available balance
            if amount > available_balance * Decimal("0.95"):
                warnings.append("Order sells more than 95% of available balance")

        return OrderValidationResult(is_valid=True, warnings=warnings)

    def _validate_precision(self,
                            trading_rule: TradingRule,
                            amount: Decimal,
                            price: Optional[Decimal]) -> OrderValidationResult:
        """
        Validate and adjust precision for amount and price.

        Args:
            trading_rule: Trading rule for the pair
            amount: Order amount
            price: Order price

        Returns:
            OrderValidationResult with adjusted values
        """
        warnings = []
        adjusted_amount = amount
        adjusted_price = price

        # Adjust amount precision
        amount_increment = trading_rule.min_base_amount_increment
        if amount_increment > 0:
            # Round to nearest increment
            adjusted_amount = (amount / amount_increment).quantize(Decimal("1")) * amount_increment

            if adjusted_amount != amount:
                warnings.append(f"Amount adjusted from {amount} to {adjusted_amount} for precision")

        # Adjust price precision
        if price is not None:
            price_increment = trading_rule.min_price_increment
            if price_increment > 0:
                # Round to nearest increment
                adjusted_price = (price / price_increment).quantize(Decimal("1")) * price_increment

                if adjusted_price != price:
                    warnings.append(f"Price adjusted from {price} to {adjusted_price} for precision")

        # Check significant digits
        if len(str(adjusted_amount).replace(".", "").lstrip("0")) > trading_rule.max_base_amount_significant_digits:
            warnings.append(f"Amount may have too many significant digits (max {trading_rule.max_base_amount_significant_digits})")

        if adjusted_price is not None:
            if len(str(adjusted_price).replace(".", "").lstrip("0")) > trading_rule.max_price_significant_digits:
                warnings.append(f"Price may have too many significant digits (max {trading_rule.max_price_significant_digits})")

        return OrderValidationResult(
            is_valid=True,
            warnings=warnings,
            adjusted_amount=adjusted_amount,
            adjusted_price=adjusted_price
        )

    def _get_trading_rule(self, trading_pair: str) -> TradingRule:
        """
        Get trading rule for a trading pair.

        Args:
            trading_pair: Trading pair

        Returns:
            TradingRule object
        """
        return self._trading_rules.get(trading_pair, self._default_rules)

    def update_trading_rules(self, trading_rules: Dict[str, TradingRule]):
        """
        Update trading rules from exchange info.

        Args:
            trading_rules: Dictionary of trading rules
        """
        self._trading_rules.update(trading_rules)
        self.logger().info(f"Updated trading rules for {len(trading_rules)} trading pairs")

    def get_trading_rule(self, trading_pair: str) -> Optional[TradingRule]:
        """
        Get trading rule for a specific trading pair.

        Args:
            trading_pair: Trading pair

        Returns:
            TradingRule or None if not found
        """
        return self._trading_rules.get(trading_pair)

    def validate_order_modification(self,
                                    original_amount: Decimal,
                                    original_price: Optional[Decimal],
                                    new_amount: Decimal,
                                    new_price: Optional[Decimal],
                                    trading_pair: str) -> OrderValidationResult:
        """
        Validate order modification parameters.

        Args:
            original_amount: Original order amount
            original_price: Original order price
            new_amount: New order amount
            new_price: New order price
            trading_pair: Trading pair

        Returns:
            OrderValidationResult
        """
        # Check if modification is significant enough
        amount_change_pct = abs(new_amount - original_amount) / original_amount * 100

        if amount_change_pct < Decimal("1"):  # Less than 1% change
            return OrderValidationResult(
                is_valid=False,
                error_message="Order modification too small (less than 1% change)"
            )

        # Validate new parameters
        return self.validate_order_parameters(
            trading_pair=trading_pair,
            order_type=OrderType.LIMIT,  # Assume limit for modifications
            trade_type=TradeType.BUY,    # Trade type doesn't matter for validation
            amount=new_amount,
            price=new_price
        )

    def calculate_order_fees(self,
                             trading_pair: str,
                             order_type: OrderType,
                             trade_type: TradeType,
                             amount: Decimal,
                             price: Decimal,
                             is_maker: bool = True) -> Dict[str, Decimal]:
        """
        Calculate estimated order fees.

        Args:
            trading_pair: Trading pair
            order_type: Order type
            trade_type: Trade type
            amount: Order amount
            price: Order price
            is_maker: Whether order is maker or taker

        Returns:
            Dictionary with fee information
        """
        # Default fee rates (should be updated from exchange info)
        maker_fee_rate = Decimal("0.001")  # 0.1%
        taker_fee_rate = Decimal("0.002")  # 0.2%

        fee_rate = maker_fee_rate if is_maker else taker_fee_rate
        notional_value = amount * price
        fee_amount = notional_value * fee_rate

        # Determine fee asset
        base_asset, quote_asset = trading_pair.split("-")
        fee_asset = quote_asset if trade_type == TradeType.BUY else base_asset

        return {
            "fee_rate": fee_rate,
            "fee_amount": fee_amount,
            "fee_asset": fee_asset,
            "notional_value": notional_value,
            "is_maker": is_maker
        }

    def get_minimum_order_value(self, trading_pair: str) -> Decimal:
        """
        Get minimum order value for a trading pair.

        Args:
            trading_pair: Trading pair

        Returns:
            Minimum order value
        """
        trading_rule = self._get_trading_rule(trading_pair)
        return trading_rule.min_notional_size

    def get_order_size_limits(self, trading_pair: str) -> Tuple[Decimal, Decimal]:
        """
        Get order size limits for a trading pair.

        Args:
            trading_pair: Trading pair

        Returns:
            Tuple of (min_size, max_size)
        """
        trading_rule = self._get_trading_rule(trading_pair)
        return trading_rule.min_order_size, trading_rule.max_order_size

    def format_order_amount(self, trading_pair: str, amount: Decimal) -> Decimal:
        """
        Format order amount according to trading rules.

        Args:
            trading_pair: Trading pair
            amount: Order amount

        Returns:
            Formatted amount
        """
        from decimal import ROUND_DOWN
        
        trading_rule = self._get_trading_rule(trading_pair)
        increment = trading_rule.min_base_amount_increment

        if increment > 0:
            # Calculate number of decimal places in increment
            increment_str = str(increment)
            if '.' in increment_str:
                decimal_places = len(increment_str.split('.')[1].rstrip('0'))
            else:
                decimal_places = 0
            
            # Quantize to the increment precision using ROUND_DOWN
            quantize_str = '0.' + '0' * decimal_places if decimal_places > 0 else '1'
            return amount.quantize(Decimal(quantize_str), rounding=ROUND_DOWN)

        return amount

    def format_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Format order price according to trading rules.

        Args:
            trading_pair: Trading pair
            price: Order price

        Returns:
            Formatted price
        """
        from decimal import ROUND_DOWN
        
        trading_rule = self._get_trading_rule(trading_pair)
        increment = trading_rule.min_price_increment

        if increment > 0:
            # Calculate number of decimal places in increment
            increment_str = str(increment)
            if '.' in increment_str:
                decimal_places = len(increment_str.split('.')[1].rstrip('0'))
            else:
                decimal_places = 0
            
            # Quantize to the increment precision using ROUND_DOWN
            quantize_str = '0.' + '0' * decimal_places if decimal_places > 0 else '1'
            return price.quantize(Decimal(quantize_str), rounding=ROUND_DOWN)

        return price

    def validate_order(self, order_data: Dict[str, Any]) -> OrderValidationResult:
        """
        Validate order data.

        Args:
            order_data: Order data dictionary

        Returns:
            OrderValidationResult
        """
        try:
            # Extract order parameters
            symbol = order_data.get("symbol", "")
            trading_pair = order_data.get("trading_pair", symbol)
            order_type = order_data.get("order_type", OrderType.LIMIT)
            trade_type = order_data.get("side", TradeType.BUY)
            quantity = order_data.get("quantity", Decimal("0"))
            price = order_data.get("price")

            # Validate symbol exists in trading rules
            if trading_pair not in self._trading_rules and symbol not in self._trading_rules:
                return OrderValidationResult(
                    is_valid=False,
                    error_message=f"Unknown symbol: {symbol or trading_pair}"
                )

            # Validate using existing method
            return self.validate_order_parameters(
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                amount=quantity,
                price=price
            )

        except Exception as e:
            return OrderValidationResult(
                is_valid=False,
                error_message=f"Validation error: {e}"
            )

    def quantize_order_amount(self, trading_pair: str, amount: Decimal) -> Decimal:
        """
        Quantize order amount according to trading rules.

        Args:
            trading_pair: Trading pair
            amount: Order amount

        Returns:
            Quantized amount
        """
        return self.format_order_amount(trading_pair, amount)

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Quantize order price according to trading rules.

        Args:
            trading_pair: Trading pair
            price: Order price

        Returns:
            Quantized price
        """
        return self.format_order_price(trading_pair, price)
