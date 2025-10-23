#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Order Validation
"""

import unittest
from decimal import Decimal

from hummingbot.connector.exchange.coinsxyz.coinsxyz_order_validation import CoinsxyzOrderValidation
from hummingbot.core.data_type.common import OrderType, TradeType


class TestCoinsxyzOrderValidation(unittest.TestCase):
    """Unit tests for CoinsxyzOrderValidation."""

    def setUp(self):
        """Set up test fixtures."""
        from hummingbot.connector.exchange.coinsxyz.coinsxyz_order_validation import TradingRule
        self.trading_rules = {
            "BTC-USDT": TradingRule(
                trading_pair="BTC-USDT",
                min_order_size=Decimal("0.001"),
                max_order_size=Decimal("1000"),
                min_price_increment=Decimal("0.01"),
                min_base_amount_increment=Decimal("0.000001"),
                min_quote_amount_increment=Decimal("0.01"),
                min_notional_size=Decimal("10.0"),
                max_price_significant_digits=8,
                max_base_amount_significant_digits=8
            ),
            "BTCUSDT": TradingRule(
                trading_pair="BTCUSDT",
                min_order_size=Decimal("0.001"),
                max_order_size=Decimal("1000"),
                min_price_increment=Decimal("0.01"),
                min_base_amount_increment=Decimal("0.000001"),
                min_quote_amount_increment=Decimal("0.01"),
                min_notional_size=Decimal("10.0"),
                max_price_significant_digits=8,
                max_base_amount_significant_digits=8
            )
        }
        self.validator = CoinsxyzOrderValidation()
        self.validator.update_trading_rules(self.trading_rules)

    def test_init(self):
        """Test validator initialization."""
        self.assertIsNotNone(self.validator._trading_rules)

    def test_validate_order_parameters(self):
        """Test order parameter validation."""
        # Valid order
        result = self.validator.validate_order_parameters(
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1.0"),
            price=Decimal("50000.0")
        )
        self.assertTrue(result.is_valid)

        # Too small amount
        result = self.validator.validate_order_parameters(
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("0.0001"),
            price=Decimal("50000.0")
        )
        self.assertFalse(result.is_valid)

    def test_format_order_price(self):
        """Test order price formatting."""
        # Valid price formatting
        formatted = self.validator.format_order_price(
            "BTC-USDT", Decimal("50000.123")
        )
        self.assertEqual(formatted, Decimal("50000.12"))

    def test_validate_limit_order(self):
        """Test limit order validation."""
        valid_order = {
            "symbol": "BTCUSDT",
            "side": TradeType.BUY,
            "order_type": OrderType.LIMIT,
            "quantity": Decimal("1.0"),
            "price": Decimal("50000.00")
        }

        result = self.validator.validate_order(valid_order)
        self.assertTrue(result.is_valid)

    def test_validate_market_order(self):
        """Test market order validation."""
        valid_order = {
            "symbol": "BTCUSDT",
            "side": TradeType.SELL,
            "order_type": OrderType.MARKET,
            "quantity": Decimal("0.5")
        }

        result = self.validator.validate_order(valid_order)
        self.assertTrue(result.is_valid)

    def test_validate_invalid_symbol(self):
        """Test validation with invalid symbol."""
        invalid_order = {
            "symbol": "INVALID",
            "side": TradeType.BUY,
            "order_type": OrderType.LIMIT,
            "quantity": Decimal("1.0"),
            "price": Decimal("50000.00")
        }

        result = self.validator.validate_order(invalid_order)
        self.assertFalse(result.is_valid)
        self.assertIn("Unknown symbol", result.error_message)

    def test_quantize_order_amount(self):
        """Test order amount quantization."""
        amount = Decimal("1.123456789")
        quantized = self.validator.quantize_order_amount("BTCUSDT", amount)

        self.assertEqual(quantized, Decimal("1.123456"))

    def test_quantize_order_price(self):
        """Test order price quantization."""
        price = Decimal("50000.123")
        quantized = self.validator.quantize_order_price("BTCUSDT", price)

        self.assertEqual(quantized, Decimal("50000.12"))


if __name__ == "__main__":
    unittest.main()
