import unittest

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS
from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils


class TestBackpackWebUtils(unittest.TestCase):
    """Test suite for Backpack web utilities."""

    def test_rest_url_mainnet(self):
        """Test REST URL generation for mainnet."""
        url = web_utils.rest_url(CONSTANTS.MARKETS_URL, CONSTANTS.DOMAIN)

        self.assertEqual(f"{CONSTANTS.BASE_URL}{CONSTANTS.MARKETS_URL}", url)

    def test_rest_url_testnet(self):
        """Test REST URL generation for testnet."""
        url = web_utils.rest_url(CONSTANTS.MARKETS_URL, CONSTANTS.TESTNET_DOMAIN)

        self.assertEqual(f"{CONSTANTS.TESTNET_BASE_URL}{CONSTANTS.MARKETS_URL}", url)

    def test_wss_url_mainnet(self):
        """Test WebSocket URL generation for mainnet."""
        url = web_utils.wss_url(CONSTANTS.DOMAIN)

        self.assertEqual(CONSTANTS.WS_URL, url)

    def test_wss_url_testnet(self):
        """Test WebSocket URL generation for testnet."""
        url = web_utils.wss_url(CONSTANTS.TESTNET_DOMAIN)

        self.assertEqual(CONSTANTS.TESTNET_WS_URL, url)

    def test_build_api_factory(self):
        """Test API factory creation."""
        factory = web_utils.build_api_factory(throttler=None, auth=None)

        self.assertIsNotNone(factory)

    def test_rest_url_with_various_endpoints(self):
        """Test REST URL generation for various endpoints."""
        endpoints = [
            CONSTANTS.MARKETS_URL,
            CONSTANTS.ORDER_URL,
            CONSTANTS.CAPITAL_URL,
            CONSTANTS.TICKER_URL,
            CONSTANTS.DEPTH_URL,
        ]

        for endpoint in endpoints:
            url = web_utils.rest_url(endpoint, CONSTANTS.DOMAIN)
            self.assertTrue(url.startswith(CONSTANTS.BASE_URL))
            self.assertTrue(url.endswith(endpoint))


if __name__ == "__main__":
    unittest.main()
