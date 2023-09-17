from unittest import TestCase

from hummingbot.connector.exchange.woo_x import woo_x_constants as CONSTANTS, woo_x_web_utils as web_utils


class WebUtilsTests(TestCase):
    def test_rest_url(self):
        url = web_utils.public_rest_url(path_url=CONSTANTS.MARKET_TRADES_PATH, domain=CONSTANTS.DEFAULT_DOMAIN)
        self.assertEqual('https://api.woo.org/v1/public/market_trades', url)
        url = web_utils.public_rest_url(path_url=CONSTANTS.MARKET_TRADES_PATH, domain='woo_x_testnet')
        self.assertEqual('https://api.staging.woo.org/v1/public/market_trades', url)
