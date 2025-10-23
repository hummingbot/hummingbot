#!/usr/bin/env python3

import unittest
from decimal import Decimal
from unittest.mock import MagicMock

from hummingbot.connector.exchange.coinsxyz.coinsxyz_order_lifecycle import CoinsxyzOrderLifecycle


class TestCoinsxyzOrderLifecycle(unittest.TestCase):
    """Unit tests for CoinsxyzOrderLifecycle."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock API factory
        self.mock_api_factory = MagicMock()
        self.order_lifecycle = CoinsxyzOrderLifecycle(api_factory=self.mock_api_factory)

    def test_init(self):
        """Test order lifecycle initialization."""
        self.assertIsNotNone(self.order_lifecycle)

    def test_create_order_request(self):
        """Test order request creation."""
        order_params = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "quantity": "1.0",
            "price": "50000.0"
        }

        request = self.order_lifecycle.create_order_request(order_params)

        self.assertIsInstance(request, dict)
        self.assertEqual(request["symbol"], "BTCUSDT")
        self.assertEqual(request["side"], "BUY")

    def test_validate_order_params(self):
        """Test order parameter validation."""
        valid_params = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "quantity": "1.0",
            "price": "50000.0"
        }
        self.assertTrue(self.order_lifecycle.validate_order_params(valid_params))

        invalid_params = {"symbol": ""}
        self.assertFalse(self.order_lifecycle.validate_order_params(invalid_params))

    def test_process_order_update(self):
        """Test order update processing."""
        order_update = {
            "orderId": "12345",
            "status": "FILLED",
            "executedQty": "1.0",
            "cummulativeQuoteQty": "50000.0"
        }

        processed = self.order_lifecycle.process_order_update(order_update)

        self.assertIsInstance(processed, dict)
        self.assertEqual(processed["order_id"], "12345")
        self.assertEqual(processed["status"], "FILLED")

    def test_calculate_order_fees(self):
        """Test order fee calculation."""
        trade_amount = Decimal("1000.0")
        fee_rate = Decimal("0.001")  # 0.1%

        fee = self.order_lifecycle.calculate_order_fees(trade_amount, fee_rate)

        self.assertEqual(fee, Decimal("1.0"))
        self.assertIsInstance(fee, Decimal)

    def test_is_order_complete(self):
        """Test order completion check."""
        complete_order = {"status": "FILLED"}
        self.assertTrue(self.order_lifecycle.is_order_complete(complete_order))

        incomplete_order = {"status": "NEW"}
        self.assertFalse(self.order_lifecycle.is_order_complete(incomplete_order))


if __name__ == "__main__":
    unittest.main()
