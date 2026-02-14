from unittest import TestCase

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS
from hummingbot.connector.exchange.gemini.gemini_web_utils import (
    create_throttler,
    public_rest_url,
    private_rest_url,
    wss_url,
)


class GeminiWebUtilsTests(TestCase):

    def test_public_rest_url(self):
        url = public_rest_url(CONSTANTS.SYMBOLS_PATH_URL)
        self.assertEqual("https://api.gemini.com/v1/symbols", url)

    def test_private_rest_url(self):
        url = private_rest_url(CONSTANTS.NEW_ORDER_PATH_URL)
        self.assertEqual("https://api.gemini.com/v1/order/new", url)

    def test_wss_url(self):
        url = wss_url()
        self.assertEqual("wss://wsapi.fast.gemini.com", url)

    def test_create_throttler(self):
        throttler = create_throttler()
        self.assertIsNotNone(throttler)
