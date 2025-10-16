#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Trading Rules
"""

import unittest
from decimal import Decimal
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from hummingbot.connector.exchange.coinsxyz.coinsxyz_trading_rules import CoinsxyzTradingRules


class TestCoinsxyzTradingRules(unittest.TestCase):
    """Unit tests for CoinsxyzTradingRules."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_client = MagicMock()
        self.trading_rules = CoinsxyzTradingRules(api_client=self.api_client)

    def test_init(self):
        """Test trading rules initialization."""
        self.assertIsNotNone(self.trading_rules._api_client)
        self.assertEqual(len(self.trading_rules._rules), 0)

    async def test_update_trading_rules(self):
        """Test trading rules update."""
        mock_exchange_info = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "filters": [
                        {
                            "filterType": "LOT_SIZE",
                            "minQty": "0.001",
                            "maxQty": "1000",
                            "stepSize": "0.000001"
                        },
                        {
                            "filterType": "PRICE_FILTER",
                            "minPrice": "0.01",
                            "maxPrice": "1000000",
                            "tickSize": "0.01"
                        }
                    ]
                }
            ]
        }

        self.api_client.get_exchange_info = AsyncMock(return_value=mock_exchange_info)

        await self.trading_rules.update_trading_rules()

        self.assertIn("BTCUSDT", self.trading_rules._rules)
        rule = self.trading_rules._rules["BTCUSDT"]
        self.assertEqual(rule.min_order_size, Decimal("0.001"))
        self.assertEqual(rule.min_price_increment, Decimal("0.01"))

    def test_get_trading_rule(self):
        """Test getting trading rule for symbol."""
        # Add mock rule
        self.trading_rules._rules["BTCUSDT"] = MagicMock()
        self.trading_rules._rules["BTCUSDT"].min_order_size = Decimal("0.001")

        rule = self.trading_rules.get_trading_rule("BTCUSDT")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.min_order_size, Decimal("0.001"))

        # Test non-existent symbol
        rule = self.trading_rules.get_trading_rule("INVALID")
        self.assertIsNone(rule)

    def test_parse_lot_size_filter(self):
        """Test LOT_SIZE filter parsing."""
        filter_data = {
            "filterType": "LOT_SIZE",
            "minQty": "0.001",
            "maxQty": "1000",
            "stepSize": "0.000001"
        }

        min_size, max_size, step_size = self.trading_rules._parse_lot_size_filter(filter_data)

        self.assertEqual(min_size, Decimal("0.001"))
        self.assertEqual(max_size, Decimal("1000"))
        self.assertEqual(step_size, Decimal("0.000001"))

    def test_parse_price_filter(self):
        """Test PRICE_FILTER parsing."""
        filter_data = {
            "filterType": "PRICE_FILTER",
            "minPrice": "0.01",
            "maxPrice": "1000000",
            "tickSize": "0.01"
        }

        min_price, max_price, tick_size = self.trading_rules._parse_price_filter(filter_data)

        self.assertEqual(min_price, Decimal("0.01"))
        self.assertEqual(max_price, Decimal("1000000"))
        self.assertEqual(tick_size, Decimal("0.01"))

    def test_is_symbol_supported(self):
        """Test symbol support check."""
        self.trading_rules._rules["BTCUSDT"] = MagicMock()

        self.assertTrue(self.trading_rules.is_symbol_supported("BTCUSDT"))
        self.assertFalse(self.trading_rules.is_symbol_supported("INVALID"))

    def test_get_all_symbols(self):
        """Test getting all supported symbols."""
        self.trading_rules._rules["BTCUSDT"] = MagicMock()
        self.trading_rules._rules["ETHUSDT"] = MagicMock()

        symbols = self.trading_rules.get_all_symbols()

        self.assertIn("BTCUSDT", symbols)
        self.assertIn("ETHUSDT", symbols)
        self.assertEqual(len(symbols), 2)


if __name__ == "__main__":
    unittest.main()
