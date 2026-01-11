import unittest

from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_utils import (
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
)


class TestEvedexPerpetualUtils(unittest.TestCase):

    def test_convert_from_exchange_trading_pair(self):
        result = convert_from_exchange_trading_pair("BTC-USDT")
        self.assertIsNotNone(result)

    def test_convert_to_exchange_trading_pair(self):
        result = convert_to_exchange_trading_pair("BTC-USDT")
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
