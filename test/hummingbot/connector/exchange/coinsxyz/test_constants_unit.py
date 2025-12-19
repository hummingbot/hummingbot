#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz Constants
"""

import unittest

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.core.data_type.in_flight_order import OrderState


class TestCoinsxyzConstants(unittest.TestCase):
    """Unit tests for CoinsxyzConstants."""

    def test_exchange_name(self):
        """Test exchange name constant."""
        self.assertEqual(CONSTANTS.EXCHANGE_NAME, "coinsxyz")

    def test_default_domain(self):
        """Test default domain."""
        self.assertEqual(CONSTANTS.DEFAULT_DOMAIN, "com")

    def test_api_urls(self):
        """Test API URLs."""
        self.assertTrue(CONSTANTS.REST_URL.startswith("https://"))
        self.assertTrue(CONSTANTS.WSS_URL.startswith("wss://"))

    def test_order_states_mapping(self):
        """Test order states mapping."""
        self.assertIn("NEW", CONSTANTS.ORDER_STATE)
        self.assertIn("FILLED", CONSTANTS.ORDER_STATE)
        self.assertIn("CANCELED", CONSTANTS.ORDER_STATE)

        self.assertEqual(CONSTANTS.ORDER_STATE["NEW"], OrderState.OPEN)
        self.assertEqual(CONSTANTS.ORDER_STATE["FILLED"], OrderState.FILLED)
        self.assertEqual(CONSTANTS.ORDER_STATE["CANCELED"], OrderState.CANCELED)

    def test_rate_limits(self):
        """Test rate limits configuration."""
        self.assertIsInstance(CONSTANTS.RATE_LIMITS, list)
        self.assertGreater(len(CONSTANTS.RATE_LIMITS), 0)

    def test_endpoints(self):
        """Test API endpoints."""
        self.assertEqual(CONSTANTS.PING_PATH_URL, "/ping")
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_PATH_URL, "/exchangeInfo")
        self.assertEqual(CONSTANTS.ORDER_PATH_URL, "/order")
        self.assertEqual(CONSTANTS.ACCOUNTS_PATH_URL, "/account")

    def test_order_sides(self):
        """Test order sides."""
        self.assertEqual(CONSTANTS.SIDE_BUY, "BUY")
        self.assertEqual(CONSTANTS.SIDE_SELL, "SELL")

    def test_time_in_force(self):
        """Test time in force values."""
        self.assertEqual(CONSTANTS.TIME_IN_FORCE_GTC, "GTC")
        self.assertEqual(CONSTANTS.TIME_IN_FORCE_IOC, "IOC")
        self.assertEqual(CONSTANTS.TIME_IN_FORCE_FOK, "FOK")

    def test_error_codes(self):
        """Test error codes."""
        self.assertEqual(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE, -2013)
        self.assertEqual(CONSTANTS.UNKNOWN_ORDER_ERROR_CODE, -2011)
        self.assertEqual(CONSTANTS.INSUFFICIENT_BALANCE_ERROR_CODE, -2010)

    def test_websocket_events(self):
        """Test WebSocket event types."""
        self.assertEqual(CONSTANTS.DIFF_EVENT_TYPE, "depthUpdate")
        self.assertEqual(CONSTANTS.TRADE_EVENT_TYPE, "trade")
        self.assertEqual(CONSTANTS.ORDER_UPDATE_EVENT_TYPE, "executionReport")

    def test_is_exchange_information_valid(self):
        """Test exchange information validation."""
        valid_info = {
            "status": "TRADING",
            "isSpotTradingAllowed": True,
            "permissions": ["SPOT"]
        }
        # is_exchange_information_valid is a function, not a method
        from hummingbot.connector.exchange.coinsxyz.coinsxyz_constants import is_exchange_information_valid
        self.assertTrue(is_exchange_information_valid(valid_info))

        invalid_info = {
            "status": "BREAK",
            "isSpotTradingAllowed": False,
            "permissions": []
        }
        self.assertFalse(is_exchange_information_valid(invalid_info))


if __name__ == "__main__":
    unittest.main()
