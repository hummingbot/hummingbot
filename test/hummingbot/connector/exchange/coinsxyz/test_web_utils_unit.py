#!/usr/bin/env python3

import unittest

from hummingbot.connector.exchange.coinsxyz.coinsxyz_web_utils import CoinsxyzWebUtils


class TestCoinsxyzWebUtils(unittest.TestCase):
    """Unit tests for CoinsxyzWebUtils."""

    def setUp(self):
        """Set up test fixtures."""
        self.web_utils = CoinsxyzWebUtils()

    def test_init(self):
        """Test web utils initialization."""
        self.assertIsNotNone(self.web_utils)

    def test_build_api_url(self):
        """Test API URL construction."""
        endpoint = "/account"
        url = self.web_utils.build_api_url(endpoint)

        self.assertIsInstance(url, str)
        self.assertTrue(url.endswith(endpoint))
        self.assertTrue(url.startswith("https://"))

    def test_format_trading_pair(self):
        """Test trading pair formatting."""
        # Test Hummingbot format to exchange format
        hb_pair = "BTC-USDT"
        exchange_pair = self.web_utils.format_trading_pair(hb_pair, to_exchange=True)
        self.assertEqual(exchange_pair, "BTCUSDT")

        # Test exchange format to Hummingbot format
        exchange_pair = "BTCUSDT"
        hb_pair = self.web_utils.format_trading_pair(exchange_pair, to_exchange=False)
        self.assertEqual(hb_pair, "BTC-USDT")

    def test_validate_response(self):
        """Test API response validation."""
        valid_response = {"status": "success", "data": {}}
        self.assertTrue(self.web_utils.validate_response(valid_response))

        invalid_response = {"error": "Invalid request"}
        self.assertFalse(self.web_utils.validate_response(invalid_response))

    def test_parse_timestamp(self):
        """Test timestamp parsing."""
        timestamp_ms = 1640995200000  # 2022-01-01 00:00:00 UTC
        parsed = self.web_utils.parse_timestamp(timestamp_ms)

        self.assertIsInstance(parsed, float)
        self.assertEqual(parsed, 1640995200.0)

    def test_create_request_headers(self):
        """Test request headers creation."""
        headers = self.web_utils.create_request_headers()

        self.assertIsInstance(headers, dict)
        self.assertIn("Content-Type", headers)
        self.assertIn("User-Agent", headers)


if __name__ == "__main__":
    unittest.main()
