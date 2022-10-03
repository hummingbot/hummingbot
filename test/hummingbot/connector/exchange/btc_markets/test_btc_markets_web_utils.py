from unittest import TestCase

from hummingbot.connector.exchange.btc_markets import (
    btc_markets_constants as CONSTANTS,
    btc_markets_web_utils as web_utils,
)


class WebUtilsTest(TestCase):
    def test_public_rest_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADES_URL, domain=CONSTANTS.DEFAULT_DOMAIN)
        self.assertEqual('https://api.btcmarkets.net/v3/trades', url)

    def test_private_rest_url(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.TRADES_URL)
        self.assertEqual('https://api.btcmarkets.net/v3/trades', url)

    def test_get_path_from_url(self):
        url = web_utils.get_path_from_url('https://api.btcmarkets.net/v3/trades')
        self.assertEqual('v3/trades', url)
