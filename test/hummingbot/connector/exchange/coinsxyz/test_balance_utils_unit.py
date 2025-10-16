#!/usr/bin/env python3

import unittest
from decimal import Decimal

from hummingbot.connector.exchange.coinsxyz.coinsxyz_balance_utils import CoinsxyzBalanceUtils


class TestCoinsxyzBalanceUtils(unittest.TestCase):
    """Unit tests for CoinsxyzBalanceUtils."""

    def setUp(self):
        """Set up test fixtures."""
        self.balance_utils = CoinsxyzBalanceUtils()

    def test_init(self):
        """Test balance utils initialization."""
        self.assertIsNotNone(self.balance_utils)

    def test_parse_balance_response(self):
        """Test balance response parsing."""
        balance_data = {
            "balances": [
                {"asset": "BTC", "free": "1.0", "locked": "0.5"},
                {"asset": "USDT", "free": "1000.0", "locked": "100.0"}
            ]
        }

        parsed = self.balance_utils.parse_balance_response(balance_data)

        self.assertIsInstance(parsed, dict)
        self.assertIn("BTC", parsed)
        self.assertIn("USDT", parsed)

    def test_calculate_total_balance(self):
        """Test total balance calculation."""
        free_balance = Decimal("1.0")
        locked_balance = Decimal("0.5")

        total = self.balance_utils.calculate_total_balance(free_balance, locked_balance)

        self.assertEqual(total, Decimal("1.5"))
        self.assertIsInstance(total, Decimal)

    def test_validate_balance_data(self):
        """Test balance data validation."""
        valid_data = {"asset": "BTC", "free": "1.0", "locked": "0.5"}
        self.assertTrue(self.balance_utils.validate_balance_data(valid_data))

        invalid_data = {"asset": "BTC"}
        self.assertFalse(self.balance_utils.validate_balance_data(invalid_data))

    def test_format_balance_for_display(self):
        """Test balance formatting for display."""
        balance = Decimal("1.23456789")
        formatted = self.balance_utils.format_balance_for_display(balance, precision=4)

        self.assertIsInstance(formatted, str)
        self.assertEqual(formatted, "1.2346")


if __name__ == "__main__":
    unittest.main()
