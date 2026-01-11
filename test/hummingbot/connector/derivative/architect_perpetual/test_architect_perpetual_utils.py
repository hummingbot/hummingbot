import unittest

from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_utils import (
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    split_trading_pair,
    is_exchange_information_valid,
)


class TestArchitectPerpetualUtils(unittest.TestCase):

    def test_convert_from_exchange_trading_pair_crypto(self):
        self.assertEqual(convert_from_exchange_trading_pair("BTC Crypto/USD"), "BTC-USD")

    def test_convert_from_exchange_trading_pair_futures(self):
        self.assertEqual(convert_from_exchange_trading_pair("ES/USD"), "ES-USD")

    def test_convert_from_exchange_trading_pair_already_hb_format(self):
        self.assertEqual(convert_from_exchange_trading_pair("BTC-USD"), "BTC-USD")

    def test_convert_to_exchange_trading_pair_crypto(self):
        self.assertEqual(convert_to_exchange_trading_pair("BTC-USD", venue="COINBASE"), "BTC Crypto/USD")

    def test_convert_to_exchange_trading_pair_futures(self):
        self.assertEqual(convert_to_exchange_trading_pair("ES-USD", venue="CME"), "ES/USD")

    def test_split_trading_pair_hb_format(self):
        base, quote = split_trading_pair("BTC-USD")
        self.assertEqual(base, "BTC")
        self.assertEqual(quote, "USD")

    def test_split_trading_pair_exchange_format(self):
        base, quote = split_trading_pair("BTC Crypto/USD")
        self.assertEqual(base, "BTC")
        self.assertEqual(quote, "USD")

    def test_is_exchange_information_valid_true(self):
        self.assertTrue(is_exchange_information_valid({"symbols": [{"symbol": "BTC-USD"}]}))

    def test_is_exchange_information_valid_false_none(self):
        self.assertFalse(is_exchange_information_valid(None))

    def test_is_exchange_information_valid_false_no_symbols(self):
        self.assertFalse(is_exchange_information_valid({"markets": []}))


if __name__ == "__main__":
    unittest.main()
