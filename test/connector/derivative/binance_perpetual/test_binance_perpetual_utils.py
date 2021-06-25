import unittest

import requests

import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_utils as utils
from hummingbot.connector.derivative.binance_perpetual.constants import \
    TESTNET_BASE_URL, PERPETUAL_BASE_URL
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_api_order_book_data_source import (
    EXCHANGE_INFO_URL
)


class TradingPairUtilsTest(unittest.TestCase):
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

    def test_binance_testnet_pair_parsing(self):
        url = EXCHANGE_INFO_URL.format(TESTNET_BASE_URL)
        resp = requests.get(url)
        data = resp.json()
        pairs = [
            d for d in data["symbols"]
            if d["status"] == "TRADING" and d["pair"] != "CRVUSDT"
        ]
        for p in pairs:
            parsed_pair = utils.convert_from_exchange_trading_pair(p["pair"])
            expected_pair = f"{p['baseAsset']}-{p['quoteAsset']}"
            self.assertEqual(parsed_pair, expected_pair)

    def test_binance_perpetual_pair_parsing(self):
        url = EXCHANGE_INFO_URL.format(PERPETUAL_BASE_URL)
        resp = requests.get(url)
        data = resp.json()
        pairs = [
            d for d in data["symbols"]
            if d["status"] == "TRADING" and d["pair"] != "CRVUSDT"
        ]
        for p in pairs:
            parsed_pair = utils.convert_from_exchange_trading_pair(p["pair"])
            expected_pair = f"{p['baseAsset']}-{p['quoteAsset']}"
            self.assertEqual(parsed_pair, expected_pair)


if __name__ == '__main__':
    unittest.main()
