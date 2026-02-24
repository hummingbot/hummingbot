from unittest import TestCase

from hummingbot.connector.derivative.grvt_perpetual import grvt_utils


class GrvtUtilsTests(TestCase):
    def test_exchange_information_validation(self):
        self.assertTrue(grvt_utils.is_exchange_information_valid({"symbol": "BTC-USDC", "status": "active"}))
        self.assertFalse(grvt_utils.is_exchange_information_valid({"status": "active"}))

    def test_connector_name(self):
        self.assertEqual("grvt_perpetual", grvt_utils.KEYS.connector)
