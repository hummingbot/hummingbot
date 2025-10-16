#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Order Utils
"""

import unittest
from decimal import Decimal

from hummingbot.connector.exchange.coinsxyz.coinsxyz_order_utils import CoinsxyzOrderUtils
from hummingbot.core.data_type.common import OrderType, TradeType


class TestCoinsxyzOrderUtils(unittest.TestCase):
    """Unit tests for CoinsxyzOrderUtils."""

    def setUp(self):
        """Set up test fixtures."""
        self.order_utils = CoinsxyzOrderUtils()

    def test_init(self):
        """Test initialization."""
        self.assertIsNotNone(self.order_utils)

    def test_build_order_params(self):
        """Test order parameters building."""
        params = self.order_utils.build_order_params(
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1.0"),
            price=Decimal("50000.0"),
            client_order_id="test_order_1"
        )

        self.assertEqual(params["symbol"], "BTCUSDT")
        self.assertEqual(params["side"], "BUY")
        self.assertEqual(params["type"], "LIMIT")
        self.assertEqual(params["quantity"], "1.0")
        self.assertEqual(params["price"], "50000.0")
        self.assertEqual(params["newClientOrderId"], "test_order_1")

    def test_build_market_order_params(self):
        """Test market order parameters."""
        params = self.order_utils.build_order_params(
            trading_pair="ETH-USDT",
            order_type=OrderType.MARKET,
            trade_type=TradeType.SELL,
            amount=Decimal("10.0"),
            client_order_id="market_order_1"
        )

        self.assertEqual(params["type"], "MARKET")
        self.assertNotIn("price", params)
        self.assertNotIn("timeInForce", params)

    def test_build_cancel_params(self):
        """Test cancel parameters building."""
        params = self.order_utils.build_cancel_params(
            trading_pair="BTC-USDT",
            client_order_id="test_order_1"
        )

        self.assertEqual(params["symbol"], "BTCUSDT")
        self.assertEqual(params["origClientOrderId"], "test_order_1")

    def test_build_cancel_params_with_exchange_id(self):
        """Test cancel parameters with exchange order ID."""
        params = self.order_utils.build_cancel_params(
            trading_pair="BTC-USDT",
            exchange_order_id="12345"
        )

        self.assertEqual(params["symbol"], "BTCUSDT")
        self.assertEqual(params["orderId"], "12345")

    def test_build_order_status_params(self):
        """Test order status parameters building."""
        params = self.order_utils.build_order_status_params(
            trading_pair="BTC-USDT",
            client_order_id="test_order_1"
        )

        self.assertEqual(params["symbol"], "BTCUSDT")
        self.assertEqual(params["origClientOrderId"], "test_order_1")

    def test_validate_order_params(self):
        """Test order parameters validation."""
        valid_params = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "quantity": "1.0",
            "price": "50000.0"
        }
        self.assertTrue(self.order_utils.validate_order_params(valid_params))

        invalid_params = {
            "symbol": "BTCUSDT",
            "side": "BUY"
            # Missing required fields
        }
        self.assertFalse(self.order_utils.validate_order_params(invalid_params))

    def test_format_order_side(self):
        """Test order side formatting."""
        self.assertEqual(self.order_utils.format_order_side(TradeType.BUY), "BUY")
        self.assertEqual(self.order_utils.format_order_side(TradeType.SELL), "SELL")

    def test_format_order_type(self):
        """Test order type formatting."""
        self.assertEqual(self.order_utils.format_order_type(OrderType.LIMIT), "LIMIT")
        self.assertEqual(self.order_utils.format_order_type(OrderType.MARKET), "MARKET")

    def test_parse_order_response(self):
        """Test order response parsing."""
        response = {
            "orderId": "12345",
            "clientOrderId": "test_order_1",
            "symbol": "BTCUSDT",
            "status": "NEW",
            "transactTime": 1234567890000
        }

        parsed = self.order_utils.parse_order_response(response)

        self.assertEqual(parsed["exchange_order_id"], "12345")
        self.assertEqual(parsed["client_order_id"], "test_order_1")
        self.assertEqual(parsed["trading_pair"], "BTC-USDT")
        self.assertEqual(parsed["status"], "NEW")

    def test_calculate_order_value(self):
        """Test order value calculation."""
        value = self.order_utils.calculate_order_value(
            amount=Decimal("1.0"),
            price=Decimal("50000.0")
        )
        self.assertEqual(value, Decimal("50000.0"))

    def test_apply_trading_rules(self):
        """Test trading rules application."""
        from hummingbot.connector.trading_rule import TradingRule

        trading_rule = TradingRule(
            trading_pair="BTC-USDT",
            min_order_size=Decimal("0.001"),
            max_order_size=Decimal("1000"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001")
        )

        # Test valid order
        adjusted = self.order_utils.apply_trading_rules(
            amount=Decimal("1.0"),
            price=Decimal("50000.12"),
            trading_rule=trading_rule
        )
        self.assertEqual(adjusted["amount"], Decimal("1.0"))
        self.assertEqual(adjusted["price"], Decimal("50000.12"))

        # Test amount below minimum
        adjusted = self.order_utils.apply_trading_rules(
            amount=Decimal("0.0005"),
            price=Decimal("50000.0"),
            trading_rule=trading_rule
        )
        self.assertEqual(adjusted["amount"], Decimal("0.001"))


if __name__ == "__main__":
    unittest.main()
