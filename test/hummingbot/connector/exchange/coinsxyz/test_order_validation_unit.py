#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Order Validation
"""

import unittest
from decimal import Decimal

from hummingbot.connector.exchange.coinsxyz.coinsxyz_order_validation import CoinsxyzOrderValidator
from hummingbot.core.data_type.common import OrderType, TradeType


class TestCoinsxyzOrderValidator(unittest.TestCase):
    """Unit tests for CoinsxyzOrderValidator."""

    def setUp(self):
        """Set up test fixtures."""
        self.trading_rules = {
            "BTCUSDT": {
                "min_order_size": Decimal("0.001"),
                "max_order_size": Decimal("1000"),
                "min_price_increment": Decimal("0.01"),
                "min_base_amount_increment": Decimal("0.000001")
            }
        }
        self.validator = CoinsxyzOrderValidator(trading_rules=self.trading_rules)

    def test_init(self):
        """Test validator initialization."""
        self.assertIsNotNone(self.validator._trading_rules)

    def test_validate_order_size(self):
        """Test order size validation."""
        # Valid size
        self.assertTrue(self.validator.validate_order_size(
            "BTCUSDT", Decimal("1.0")
        ))

        # Too small
        self.assertFalse(self.validator.validate_order_size(
            "BTCUSDT", Decimal("0.0001")
        ))

        # Too large
        self.assertFalse(self.validator.validate_order_size(
            "BTCUSDT", Decimal("2000")
        ))

    def test_validate_order_price(self):
        """Test order price validation."""
        # Valid price
        self.assertTrue(self.validator.validate_order_price(
            "BTCUSDT", Decimal("50000.00")
        ))

        # Invalid increment
        self.assertFalse(self.validator.validate_order_price(
            "BTCUSDT", Decimal("50000.001")
        ))

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
