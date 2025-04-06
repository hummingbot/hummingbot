import unittest

import hummingbot.connector.exchange.kraken.kraken_constants as CONSTANTS
from hummingbot.connector.exchange.kraken import kraken_web_utils as web_utils


class KrakenUtilTestCases(unittest.TestCase):

    def test_public_rest_url(self):
        path_url = "/TEST_PATH"
        expected_url = CONSTANTS.BASE_URL + path_url
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url))

    def test_private_rest_url(self):
        path_url = "/TEST_PATH"
        expected_url = CONSTANTS.BASE_URL + path_url
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url))

    def test_is_exchange_information_valid(self):
        invalid_info_1 = {
            "XBTUSDT": {
                "altname": "XBTUSDT.d",
                "wsname": "XBT/USDT",
                "aclass_base": "currency",
                "base": "XXBT",
                "aclass_quote": "currency",
                "quote": "USDT",
            }
        }

        self.assertFalse(web_utils.is_exchange_information_valid(invalid_info_1["XBTUSDT"]))
        valid_info_1 = {
            "XBTUSDT": {
                "altname": "XBTUSDT",
                "wsname": "XBT/USDT",
                "aclass_base": "currency",
                "base": "XXBT",
                "aclass_quote": "currency",
                "quote": "USDT",
            }
        }

        self.assertTrue(web_utils.is_exchange_information_valid(valid_info_1["XBTUSDT"]))
