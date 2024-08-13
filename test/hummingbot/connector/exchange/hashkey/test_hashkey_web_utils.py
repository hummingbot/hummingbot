from unittest import TestCase

from hummingbot.connector.exchange.hashkey import hashkey_constants as CONSTANTS, hashkey_web_utils as web_utils


class WebUtilsTests(TestCase):
    def test_rest_url(self):
        url = web_utils.rest_url(path_url=CONSTANTS.LAST_TRADED_PRICE_PATH, domain=CONSTANTS.DEFAULT_DOMAIN)
        self.assertEqual('https://api-glb.hashkey.com/quote/v1/ticker/price', url)
        url = web_utils.rest_url(path_url=CONSTANTS.LAST_TRADED_PRICE_PATH, domain='hashkey_global_testnet')
        self.assertEqual('https://api.sim.bmuxdc.com/quote/v1/ticker/price', url)
