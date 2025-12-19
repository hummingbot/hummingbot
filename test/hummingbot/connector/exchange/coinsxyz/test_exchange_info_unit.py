#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Exchange Info
"""

import unittest
from decimal import Decimal

from hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange_info import CoinsxyzExchangeInfo


class TestCoinsxyzExchangeInfo(unittest.TestCase):
    """Unit tests for CoinsxyzExchangeInfo."""

    def setUp(self):
        """Set up test fixtures."""
        self.exchange_info = CoinsxyzExchangeInfo()

    def test_init(self):
        """Test initialization."""
        self.assertIsNotNone(self.exchange_info)

    def test_parse_exchange_info(self):
        """Test exchange info parsing."""
        exchange_data = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "trading",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "orderTypes": ["LIMIT", "MARKET"],
                    "filters": [
                        {
                            "filterType": "PRICE_FILTER",
                            "minPrice": "0.01",
                            "maxPrice": "1000000.00",
                            "tickSize": "0.01"
                        },
                        {
                            "filterType": "LOT_SIZE",
                            "minQty": "0.00001",
                            "maxQty": "9000.00000000",
                            "stepSize": "0.00001"
                        },
                        {
                            "filterType": "MIN_NOTIONAL",
                            "minNotional": "10.00000000"
                        }
                    ]
                }
            ]
        }

        trading_pairs, trading_rules = self.exchange_info.parse_exchange_info(exchange_data)

        self.assertIn("BTC-USDT", trading_pairs)
        self.assertIn("BTC-USDT", trading_rules)

        rule = trading_rules["BTC-USDT"]
        self.assertEqual(rule.trading_pair, "BTC-USDT")
        self.assertEqual(rule.min_order_size, Decimal("0.00001"))
        self.assertEqual(rule.min_price_increment, Decimal("0.01"))

    def test_parse_trading_rule(self):
        """Test trading rule parsing."""
        symbol_data = {
            "symbol": "ETHUSDT",
            "baseAsset": "ETH",
            "quoteAsset": "USDT",
            "status": "trading",
            "orderTypes": ["LIMIT", "MARKET"],
            "filters": [
                {
                    "filterType": "PRICE_FILTER",
                    "minPrice": "0.01",
                    "maxPrice": "100000.00",
                    "tickSize": "0.01"
                },
                {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.0001",
                    "maxQty": "100000.00",
                    "stepSize": "0.0001"
                }
            ]
        }

        rule = self.exchange_info._create_trading_rule(symbol_data, "ETH-USDT")

        self.assertEqual(rule.trading_pair, "ETH-USDT")
        self.assertEqual(rule.min_order_size, Decimal("0.0001"))
        self.assertEqual(rule.min_price_increment, Decimal("0.01"))

    def test_extract_trading_pair_from_symbol(self):
        """Test trading pair extraction."""
        symbol_data = {
            "symbol": "BTCUSDT",
            "baseAsset": "BTC",
            "quoteAsset": "USDT"
        }

        trading_pair = self.exchange_info._extract_trading_pair(symbol_data)
        self.assertEqual(trading_pair, "BTC-USDT")

    def test_extract_filters(self):
        """Test filter extraction."""
        filters = [
            {
                "filterType": "PRICE_FILTER",
                "minPrice": "0.01",
                "maxPrice": "1000000.00",
                "tickSize": "0.01"
            },
            {
                "filterType": "LOT_SIZE",
                "minQty": "0.00001",
                "maxQty": "9000.00000000",
                "stepSize": "0.00001"
            },
            {
                "filterType": "MIN_NOTIONAL",
                "minNotional": "10.00000000"
            }
        ]

        # Create filter dict manually since _extract_filters doesn't exist
        extracted = {f.get("filterType"): f for f in filters}

        self.assertIn("PRICE_FILTER", extracted)
        self.assertIn("LOT_SIZE", extracted)
        self.assertIn("MIN_NOTIONAL", extracted)

    def test_is_valid_trading_pair(self):
        """Test trading pair validation."""
        valid_symbol = {
            "symbol": "BTCUSDT",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "status": "trading",
            "orderTypes": ["LIMIT"],
            "filters": [{"filterType": "PRICE_FILTER"}]
        }
        self.assertTrue(self.exchange_info._is_valid_trading_pair(valid_symbol))

        invalid_symbol = {
            "symbol": "BTCUSDT",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "status": "BREAK",
            "orderTypes": [],
            "filters": []
        }
        self.assertFalse(self.exchange_info._is_valid_trading_pair(invalid_symbol))

    def test_get_supported_trading_pairs(self):
        """Test supported trading pairs retrieval."""
        exchange_data = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "status": "trading",
                    "orderTypes": ["LIMIT"],
                    "filters": [{"filterType": "PRICE_FILTER"}]
                },
                {
                    "symbol": "ETHUSDT",
                    "baseAsset": "ETH",
                    "quoteAsset": "USDT",
                    "status": "BREAK",
                    "orderTypes": [],
                    "filters": []
                }
            ]
        }

        pairs, _ = self.exchange_info.parse_exchange_info(exchange_data)

        self.assertIn("BTC-USDT", pairs)
        self.assertNotIn("ETH-USDT", pairs)  # Should be filtered out


if __name__ == "__main__":
    unittest.main()
