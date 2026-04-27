import unittest

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS
from hummingbot.connector.exchange.gemini.gemini_web_utils import (
    private_rest_url,
    public_rest_url,
    wss_market_data_url,
    wss_order_events_url,
)


class TestGeminiWebUtils(unittest.TestCase):

    def test_public_rest_url_default_domain(self):
        url = public_rest_url(path_url="/v1/symbols")
        self.assertEqual("https://api.gemini.com/v1/symbols", url)

    def test_public_rest_url_sandbox(self):
        url = public_rest_url(path_url="/v1/symbols", domain="gemini_sandbox")
        self.assertEqual("https://api.sandbox.gemini.com/v1/symbols", url)

    def test_private_rest_url_default_domain(self):
        url = private_rest_url(path_url="/v1/balances")
        self.assertEqual("https://api.gemini.com/v1/balances", url)

    def test_private_rest_url_sandbox(self):
        url = private_rest_url(path_url="/v1/balances", domain="gemini_sandbox")
        self.assertEqual("https://api.sandbox.gemini.com/v1/balances", url)

    def test_wss_market_data_url_default(self):
        url = wss_market_data_url()
        self.assertEqual(CONSTANTS.WSS_MARKET_DATA_URL, url)

    def test_wss_market_data_url_sandbox(self):
        url = wss_market_data_url(domain="gemini_sandbox")
        self.assertEqual(CONSTANTS.SANDBOX_WSS_MARKET_DATA_URL, url)

    def test_wss_order_events_url_default(self):
        url = wss_order_events_url()
        self.assertEqual(CONSTANTS.WSS_ORDER_EVENTS_URL, url)

    def test_wss_order_events_url_sandbox(self):
        url = wss_order_events_url(domain="gemini_sandbox")
        self.assertEqual(CONSTANTS.SANDBOX_WSS_ORDER_EVENTS_URL, url)
