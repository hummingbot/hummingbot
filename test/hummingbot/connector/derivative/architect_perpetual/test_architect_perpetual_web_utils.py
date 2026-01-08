from unittest import TestCase

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_web_utils import (
    orders_wss_url,
    private_rest_url,
    public_rest_url,
    wss_url,
)


class ArchitectPerpetualWebUtilsTests(TestCase):
    def test_public_rest_url_production(self):
        path = "/instruments"
        result = public_rest_url(path, CONSTANTS.DOMAIN)
        self.assertEqual(result, f"{CONSTANTS.PERPETUAL_BASE_URL}/instruments")

    def test_public_rest_url_testnet(self):
        path = "/instruments"
        result = public_rest_url(path, CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(result, f"{CONSTANTS.TESTNET_BASE_URL}/instruments")

    def test_private_rest_url_production(self):
        path = "/balances"
        result = private_rest_url(path, CONSTANTS.DOMAIN)
        self.assertEqual(result, f"{CONSTANTS.PERPETUAL_BASE_URL}/balances")

    def test_private_rest_url_testnet(self):
        path = "/balances"
        result = private_rest_url(path, CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(result, f"{CONSTANTS.TESTNET_BASE_URL}/balances")

    def test_wss_url_production(self):
        result = wss_url(CONSTANTS.DOMAIN)
        self.assertEqual(result, CONSTANTS.PERPETUAL_WS_URL)

    def test_wss_url_testnet(self):
        result = wss_url(CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(result, CONSTANTS.TESTNET_WS_URL)

    def test_orders_wss_url_production(self):
        result = orders_wss_url(CONSTANTS.DOMAIN)
        self.assertEqual(result, CONSTANTS.PERPETUAL_ORDERS_WS_URL)

    def test_orders_wss_url_testnet(self):
        result = orders_wss_url(CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(result, CONSTANTS.TESTNET_ORDERS_WS_URL)

    def test_urls_are_https_or_wss(self):
        self.assertTrue(CONSTANTS.PERPETUAL_BASE_URL.startswith("https://"))
        self.assertTrue(CONSTANTS.PERPETUAL_WS_URL.startswith("wss://"))
        self.assertTrue(CONSTANTS.PERPETUAL_ORDERS_WS_URL.startswith("wss://"))
