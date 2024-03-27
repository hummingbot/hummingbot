import unittest

from hummingbot.connector.derivative.okx_perpetual import okx_perpetual_utils as utils


class OKXPerpetualWebUtilsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    def test_is_exchange_information_valid(self):
        exchange_info = {
            "instType": "SWAP",
            "ctType": "linear",
            "state": "live"
        }
        self.assertTrue(utils.is_exchange_information_valid(exchange_info))
        exchange_info = {
            "instType": "FUTURES",
            "ctType": "linear",
            "state": "live"
        }
        self.assertFalse(utils.is_exchange_information_valid(exchange_info))

    def test_is_linear_perpetual(self):
        self.assertTrue(utils.is_linear_perpetual("BTC-USDT"))
        self.assertTrue(utils.is_linear_perpetual("BTC-USDC"))
        self.assertFalse(utils.is_linear_perpetual("BTC-USD"))

    def test_get_next_funding_timestamp(self):
        current_timestamp = 1626192000.0
        self.assertEqual(utils.get_next_funding_timestamp(current_timestamp), 1626220800.0)
