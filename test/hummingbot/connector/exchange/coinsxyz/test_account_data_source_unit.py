#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Account Data Source
"""

import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.coinsxyz.coinsxyz_account_data_source import (
    AccountBalance,
    CoinsxyzAccountDataSource,
)


class TestCoinsxyzAccountDataSource(unittest.TestCase):
    """Unit tests for CoinsxyzAccountDataSource."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_factory = MagicMock()
        self.data_source = CoinsxyzAccountDataSource(self.api_factory)

    def test_init(self):
        """Test initialization."""
        self.assertIsNotNone(self.data_source._api_factory)
        self.assertEqual(len(self.data_source._account_balances), 0)

    async def test_get_account_balances(self):
        """Test account balances retrieval."""
        mock_data = {
            "balances": [
                {"asset": "BTC", "free": "1.0", "locked": "0.5"},
                {"asset": "USDT", "free": "10000.0", "locked": "1000.0"}
            ]
        }

        with patch.object(self.data_source, '_fetch_account_balances', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_data

            balances = await self.data_source.get_account_balances()

            self.assertIn("BTC", balances)
            self.assertIn("USDT", balances)
            self.assertEqual(balances["BTC"].total_balance, Decimal("1.5"))

    async def test_get_account_balance(self):
        """Test single asset balance retrieval."""
        with patch.object(self.data_source, 'get_account_balances', new_callable=AsyncMock) as mock_get:
            mock_balance = AccountBalance("BTC", Decimal("1.5"), Decimal("1.0"), Decimal("0.5"), 123456789)
            mock_get.return_value = {"BTC": mock_balance}

            balance = await self.data_source.get_account_balance("BTC")

            self.assertEqual(balance.asset, "BTC")
            self.assertEqual(balance.total_balance, Decimal("1.5"))

    def test_parse_account_balances(self):
        """Test balance parsing."""
        balances_data = {
            "balances": [
                {"asset": "BTC", "free": "1.0", "locked": "0.5"},
                {"asset": "USDT", "free": "10000.0", "locked": "1000.0"}
            ]
        }

        parsed = self.data_source._parse_account_balances(balances_data)

        self.assertEqual(len(parsed), 2)
        self.assertIn("BTC", parsed)
        self.assertEqual(parsed["BTC"].total_balance, Decimal("1.5"))

    def test_parse_account_info(self):
        """Test account info parsing."""
        account_data = {
            "accountId": "12345",
            "accountType": "SPOT",
            "permissions": ["SPOT", "WITHDRAW"],
            "canTrade": True,
            "canWithdraw": True,
            "canDeposit": True
        }

        info = self.data_source._parse_account_info(account_data)

        self.assertEqual(info.account_id, "12345")
        self.assertTrue(info.trading_enabled)
        self.assertIn("SPOT", info.permissions)

    def test_convert_to_hummingbot_format(self):
        """Test conversion to Hummingbot format."""
        balance = AccountBalance("BTC", Decimal("1.5"), Decimal("1.0"), Decimal("0.5"), 123456789)
        balances = {"BTC": balance}

        hb_format = self.data_source.convert_to_hummingbot_format(balances)

        self.assertIn("BTC", hb_format)
        self.assertEqual(hb_format["BTC"]["total"], Decimal("1.5"))
        self.assertEqual(hb_format["BTC"]["available"], Decimal("1.0"))
        self.assertEqual(hb_format["BTC"]["locked"], Decimal("0.5"))

    def test_get_cache_status(self):
        """Test cache status."""
        status = self.data_source.get_cache_status()

        self.assertIn("balances_cached", status)
        self.assertIn("balances_cache_valid", status)
        self.assertIn("account_info_cached", status)


if __name__ == "__main__":
    unittest.main()
