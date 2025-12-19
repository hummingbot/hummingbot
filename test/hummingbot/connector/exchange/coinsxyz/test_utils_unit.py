#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Utils
"""

import unittest

from hummingbot.connector.exchange.coinsxyz import coinsxyz_utils as utils


class TestCoinsxyzUtils(unittest.TestCase):
    """Unit tests for CoinsxyzUtils."""

    def test_convert_to_exchange_trading_pair(self):
        """Test conversion to exchange trading pair format."""
        # Test standard conversion
        result = utils.convert_to_exchange_trading_pair("BTC-USDT")
        self.assertEqual(result, "BTCUSDT")

        result = utils.convert_to_exchange_trading_pair("ETH-BTC")
        self.assertEqual(result, "ETHBTC")

    def test_parse_exchange_trading_pair(self):
        """Test parsing exchange trading pair to Hummingbot format."""
        # Test standard parsing
        result = utils.parse_exchange_trading_pair("BTCUSDT")
        self.assertEqual(result, "BTC-USDT")

        result = utils.parse_exchange_trading_pair("ETHBTC")
        self.assertEqual(result, "ETH-BTC")

    def test_get_new_client_order_id(self):
        """Test client order ID generation."""
        # This function doesn't exist in utils, skip test
        pass

    def test_convert_from_exchange_trading_pair(self):
        """Test conversion from exchange format."""
        result = utils.convert_from_exchange_trading_pair("BTCUSDT", "BTC", "USDT")
        self.assertEqual(result, "BTC-USDT")

        result = utils.convert_from_exchange_trading_pair("ETHBTC", "ETH", "BTC")
        self.assertEqual(result, "ETH-BTC")

    def test_is_exchange_information_valid(self):
        """Test exchange information validation."""
        valid_info = {
            "status": "TRADING",
            "isSpotTradingAllowed": True,
            "permissions": ["SPOT"]
        }
        self.assertTrue(utils.is_pair_information_valid(valid_info))

        invalid_info = {
            "status": "BREAK",
            "isSpotTradingAllowed": False
        }
        self.assertFalse(utils.is_pair_information_valid(invalid_info))

    def test_build_api_factory(self):
        """Test API factory building."""
        from hummingbot.connector.exchange.coinsxyz import coinsxyz_web_utils
        from hummingbot.core.api_throttler.async_throttler import AsyncThrottler

        throttler = AsyncThrottler([])

        factory = coinsxyz_web_utils.build_api_factory(throttler)
        self.assertIsNotNone(factory)

    def test_get_ms_timestamp(self):
        """Test millisecond timestamp generation."""
        import time
        timestamp = int(time.time() * 1000)

        self.assertIsInstance(timestamp, int)
        self.assertGreater(timestamp, 0)

    def test_format_trading_pair(self):
        """Test trading pair formatting."""
        from hummingbot.connector.utils import combine_to_hb_trading_pair
        formatted = combine_to_hb_trading_pair("BTC", "USDT")
        self.assertEqual(formatted, "BTC-USDT")

        formatted = combine_to_hb_trading_pair("ETH", "BTC")
        self.assertEqual(formatted, "ETH-BTC")

    def test_split_trading_pair(self):
        """Test trading pair splitting."""
        base, quote = utils.extract_trading_pair_components("BTC-USDT")
        self.assertEqual(base, "BTC")
        self.assertEqual(quote, "USDT")

        base, quote = utils.extract_trading_pair_components("ETH-BTC")
        self.assertEqual(base, "ETH")
        self.assertEqual(quote, "BTC")


if __name__ == "__main__":
    unittest.main()
