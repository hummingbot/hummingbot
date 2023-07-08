import unittest

import hummingbot.connector.exchange.coinbase_advanced_trade_v2.coinbase_advanced_trade_v2_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade_v2 import coinbase_advanced_trade_v2_web_utils as web_utils


class CoinbaseAdvancedTradeV2UtilTestCases(unittest.TestCase):

    def test_public_rest_url(self):
        path_url = "/TEST_PATH"
        domain = "com"
        expected_url = CONSTANTS.REST_URL.format(domain) + CONSTANTS.PUBLIC_API_VERSION + path_url
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url, domain))

    def test_private_rest_url(self):
        path_url = "/TEST_PATH"
        domain = "com"
        expected_url = CONSTANTS.REST_URL.format(domain) + CONSTANTS.PRIVATE_API_VERSION + path_url
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url, domain))
