import unittest

from hummingbot.connector.derivative.deepcoin_perpetual import deepcoin_perpetual_utils as utils
from hummingbot.core.data_type.common import OrderType, TradeType


class DeepcoinPerpetualUtilsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    def test_is_exchange_information_valid(self):
        exchange_info = {"instType": "SWAP", "ctType": "linear", "state": "live"}
        self.assertTrue(utils.is_exchange_information_valid(exchange_info))
        exchange_info = {"instType": "FUTURES", "ctType": "linear", "state": "live"}
        self.assertFalse(utils.is_exchange_information_valid(exchange_info))

    def test_convert_from_exchange_trading_pair(self):
        symbol = "BTC-USDT-SWAP"
        self.assertEqual(utils.convert_from_exchange_trading_pair(symbol), "BTC-USDT")

    def test_convert_to_exchange_trading_pair(self):
        symbol = "BTC-USDT-SWAP"
        self.assertEqual(utils.convert_to_exchange_trading_pair("BTC-USDT"), symbol)

    def test_is_exchange_inverse(self):
        self.assertFalse(utils.is_exchange_inverse("BTC-USDT"))
        self.assertTrue(utils.is_exchange_inverse("BTC-USD"))

    def test_convert_from_exchange_order_type(self):
        self.assertEqual(utils.convert_from_exchange_order_type("limit"), OrderType.LIMIT)

    def test_convert_from_exchange_side(self):
        self.assertEqual(utils.convert_from_exchange_side("sell"), TradeType.SELL)
