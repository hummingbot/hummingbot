import unittest

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS

from hummingbot.connector.exchange.binance import binance_utils as utils


class BinanceUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def test_parse_three_letters_base_and_three_letters_quote(self):
        parsed_pair = utils.convert_from_exchange_trading_pair("BTCUSD")
        self.assertEqual(parsed_pair, "BTC-USD")

    def test_parse_three_letters_base_and_four_letters_quote(self):
        parsed_pair = utils.convert_from_exchange_trading_pair("BTCUSDT")
        self.assertEqual(parsed_pair, "BTC-USDT")

    def test_parse_three_letters_base_and_three_letters_quote_matching_with_a_four_letters_quote_candidate(self):
        parsed_pair = utils.convert_from_exchange_trading_pair("VETUSD")
        self.assertEqual(parsed_pair, "VET-USD")

    def test_convert_to_exchange_format_three_letters_base_and_three_letters_quote(self):
        converted_pair = utils.convert_to_exchange_trading_pair("BTC-USD")
        self.assertEqual(converted_pair, "BTCUSD")

    def test_convert_to_exchange_format_three_letters_base_and_four_letters_quote(self):
        converted_pair = utils.convert_to_exchange_trading_pair("BTC-USDT")
        self.assertEqual(converted_pair, "BTCUSDT")

    def test_convert_to_exchange_format_three_letters_base_and_three_letters_quote_matching_with_a_four_letters_quote_candidate(self):
        converted_pair = utils.convert_to_exchange_trading_pair("VET-USD")
        self.assertEqual(converted_pair, "VETUSD")

    def test_public_rest_url(self):
        path_url = "/TEST_PATH"
        domain = "com"
        expected_url = CONSTANTS.REST_URL.format(domain) + CONSTANTS.PUBLIC_API_VERSION + path_url
        self.assertEqual(expected_url, utils.public_rest_url(path_url, domain))

    def test_private_rest_url(self):
        path_url = "/TEST_PATH"
        domain = "com"
        expected_url = CONSTANTS.REST_URL.format(domain) + CONSTANTS.PRIVATE_API_VERSION + path_url
        self.assertEqual(expected_url, utils.private_rest_url(path_url, domain))
