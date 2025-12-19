#!/usr/bin/env python3
"""
Fixed Unit Tests for Coins.xyz Balance Utils
"""

import unittest
from decimal import Decimal

from hummingbot.connector.exchange.coinsxyz.coinsxyz_balance_utils import CoinsxyzBalanceUtils


class TestCoinsxyzBalanceUtilsFixed(unittest.TestCase):
    """Fixed unit tests for CoinsxyzBalanceUtils."""

    def setUp(self):
        """Set up test fixtures."""
        self.balance_utils = CoinsxyzBalanceUtils()

    def test_init(self):
        """Test balance utils initialization."""
        self.assertIsNotNone(self.balance_utils)

    def test_parse_balance_response(self):
        """Test balance response parsing."""
        response_data = {
            "balances": [
                {"asset": "BTC", "free": "1.0", "locked": "0.5"},
                {"asset": "USDT", "free": "1000.0", "locked": "100.0"}
            ]
        }

        parsed = self.balance_utils.parse_balance_response(response_data)

        self.assertIn("BTC", parsed)
        self.assertIn("USDT", parsed)
        self.assertEqual(parsed["BTC"]["total"], Decimal("1.5"))
        self.assertEqual(parsed["BTC"]["available"], Decimal("1.0"))
        self.assertEqual(parsed["BTC"]["locked"], Decimal("0.5"))

    def test_parse_single_balance(self):
        """Test single balance entry parsing."""
        balance_entry = {"asset": "ETH", "free": "10.0", "locked": "2.0"}

        result = self.balance_utils._parse_single_balance(balance_entry)

        self.assertIsNotNone(result)
        asset, balance_dict = result
        self.assertEqual(asset, "ETH")
        self.assertEqual(balance_dict["total"], Decimal("12.0"))
        self.assertEqual(balance_dict["available"], Decimal("10.0"))
        self.assertEqual(balance_dict["locked"], Decimal("2.0"))

    def test_extract_asset_symbol(self):
        """Test asset symbol extraction."""
        # Test different field names
        entry1 = {"asset": "BTC"}
        entry2 = {"coin": "ETH"}
        entry3 = {"currency": "USDT"}

        self.assertEqual(self.balance_utils._extract_asset_symbol(entry1), "BTC")
        self.assertEqual(self.balance_utils._extract_asset_symbol(entry2), "ETH")
        self.assertEqual(self.balance_utils._extract_asset_symbol(entry3), "USDT")

    def test_extract_balance_amount(self):
        """Test balance amount extraction."""
        entry = {
            "free": "10.5",
            "locked": "2.3",
            "total": "12.8"
        }

        available = self.balance_utils._extract_balance_amount(entry, "available")
        locked = self.balance_utils._extract_balance_amount(entry, "locked")
        total = self.balance_utils._extract_balance_amount(entry, "total")

        self.assertEqual(available, Decimal("10.5"))
        self.assertEqual(locked, Decimal("2.3"))
        self.assertEqual(total, Decimal("12.8"))

    def test_validate_balance_amounts(self):
        """Test balance amount validation."""
        # Test normal case
        total, available, locked = self.balance_utils._validate_balance_amounts(
            Decimal("10"), Decimal("8"), Decimal("2")
        )
        self.assertEqual(total, Decimal("10"))
        self.assertEqual(available, Decimal("8"))
        self.assertEqual(locked, Decimal("2"))

        # Test inconsistent amounts
        total, available, locked = self.balance_utils._validate_balance_amounts(
            Decimal("0"), Decimal("8"), Decimal("2")
        )
        self.assertEqual(total, Decimal("10"))  # Should be calculated

    def test_convert_to_hummingbot_format(self):
        """Test conversion to Hummingbot format."""
        raw_balances = {
            "balances": [
                {"asset": "BTC", "free": "1.0", "locked": "0.5"}
            ]
        }

        converted = self.balance_utils.convert_to_hummingbot_format(raw_balances)

        self.assertIn("BTC", converted)
        self.assertIn("total", converted["BTC"])
        self.assertIn("available", converted["BTC"])
        self.assertIn("locked", converted["BTC"])

    def test_calculate_balance_changes(self):
        """Test balance change calculation."""
        old_balances = {
            "BTC": {"total": Decimal("1.0"), "available": Decimal("0.8"), "locked": Decimal("0.2")}
        }
        new_balances = {
            "BTC": {"total": Decimal("1.5"), "available": Decimal("1.2"), "locked": Decimal("0.3")}
        }

        changes = self.balance_utils.calculate_balance_changes(old_balances, new_balances)

        self.assertIn("BTC", changes)
        self.assertEqual(changes["BTC"]["total"], Decimal("0.5"))
        self.assertEqual(changes["BTC"]["available"], Decimal("0.4"))
        self.assertEqual(changes["BTC"]["locked"], Decimal("0.1"))

    def test_aggregate_balances(self):
        """Test balance aggregation."""
        source1 = {
            "BTC": {"total": Decimal("1.0"), "available": Decimal("0.8"), "locked": Decimal("0.2")}
        }
        source2 = {
            "BTC": {"total": Decimal("0.5"), "available": Decimal("0.3"), "locked": Decimal("0.2")}
        }

        aggregated = self.balance_utils.aggregate_balances([source1, source2])

        self.assertEqual(aggregated["BTC"]["total"], Decimal("1.5"))
        self.assertEqual(aggregated["BTC"]["available"], Decimal("1.1"))
        self.assertEqual(aggregated["BTC"]["locked"], Decimal("0.4"))

    def test_validate_balance_consistency(self):
        """Test balance consistency validation."""
        # Valid balances
        valid_balances = {
            "BTC": {"total": Decimal("1.0"), "available": Decimal("0.8"), "locked": Decimal("0.2")}
        }
        issues = self.balance_utils.validate_balance_consistency(valid_balances)
        self.assertEqual(len(issues), 0)

        # Invalid balances
        invalid_balances = {
            "BTC": {"total": Decimal("-1.0"), "available": Decimal("0.8"), "locked": Decimal("0.2")}
        }
        issues = self.balance_utils.validate_balance_consistency(invalid_balances)
        self.assertGreater(len(issues), 0)

    def test_format_balance_for_display(self):
        """Test balance formatting for display."""
        balance_data = {
            "total": Decimal("1.23456789"),
            "available": Decimal("1.0"),
            "locked": Decimal("0.23456789")
        }

        formatted = self.balance_utils.format_balance_for_display("BTC", balance_data, precision=4)

        self.assertIn("BTC", formatted)
        self.assertIn("Total=1.2346", formatted)
        self.assertIn("Available=1.0000", formatted)
        self.assertIn("Locked=0.2346", formatted)

    def test_extract_balances_data(self):
        """Test balance data extraction from various formats."""
        # Standard format
        response1 = {"balances": [{"asset": "BTC", "free": "1.0"}]}
        data1 = self.balance_utils._extract_balances_data(response1)
        self.assertEqual(len(data1), 1)

        # Nested format
        response2 = {"data": {"balances": [{"asset": "ETH", "free": "2.0"}]}}
        data2 = self.balance_utils._extract_balances_data(response2)
        self.assertEqual(len(data2), 1)

        # List format
        response3 = [{"asset": "USDT", "free": "1000.0"}]
        data3 = self.balance_utils._extract_balances_data(response3)
        self.assertEqual(len(data3), 1)

    def test_filter_balances(self):
        """Test balance filtering."""
        balances = {
            "BTC": {"total": Decimal("1.0"), "available": Decimal("1.0"), "locked": Decimal("0")},
            "ETH": {"total": Decimal("0"), "available": Decimal("0"), "locked": Decimal("0")}
        }

        # Without zero balances
        filtered = self.balance_utils._filter_balances(balances, False)
        self.assertIn("BTC", filtered)
        self.assertNotIn("ETH", filtered)

        # With zero balances
        filtered_with_zero = self.balance_utils._filter_balances(balances, True)
        self.assertIn("BTC", filtered_with_zero)
        self.assertIn("ETH", filtered_with_zero)

    def test_is_hummingbot_format(self):
        """Test Hummingbot format detection."""
        # Valid format
        hb_format = {
            "BTC": {"total": Decimal("1.0"), "available": Decimal("0.8"), "locked": Decimal("0.2")}
        }
        self.assertTrue(self.balance_utils._is_hummingbot_format(hb_format))

        # Invalid format
        raw_format = {"balances": [{"asset": "BTC", "free": "1.0"}]}
        self.assertFalse(self.balance_utils._is_hummingbot_format(raw_format))


if __name__ == "__main__":
    unittest.main()
