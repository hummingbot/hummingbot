import unittest

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_web_utils import (
    public_rest_url,
    private_rest_url,
    wss_url,
    create_throttler,
)


class TestArchitectPerpetualWebUtils(unittest.TestCase):

    def test_public_rest_url_production(self):
        url = public_rest_url("/v1/markets", domain=CONSTANTS.DOMAIN)
        self.assertEqual(url, f"{CONSTANTS.REST_BASE_URL}/v1/markets")

    def test_public_rest_url_testnet(self):
        url = public_rest_url("/v1/markets", domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(url, f"{CONSTANTS.TESTNET_REST_BASE_URL}/v1/markets")

    def test_private_rest_url_production(self):
        url = private_rest_url("/v1/orders", domain=CONSTANTS.DOMAIN)
        self.assertEqual(url, f"{CONSTANTS.REST_BASE_URL}/v1/orders")

    def test_wss_url_production(self):
        url = wss_url(domain=CONSTANTS.DOMAIN)
        self.assertEqual(url, CONSTANTS.WS_BASE_URL)

    def test_wss_url_testnet(self):
        url = wss_url(domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(url, CONSTANTS.TESTNET_WS_BASE_URL)

    def test_create_throttler(self):
        throttler = create_throttler()
        self.assertIsNotNone(throttler)


if __name__ == "__main__":
    unittest.main()
