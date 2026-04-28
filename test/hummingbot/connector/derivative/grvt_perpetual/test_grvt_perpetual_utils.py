from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_utils as utils


class GrvtPerpetualUtilsTests(TestCase):
    def test_is_exchange_information_valid(self):
        self.assertTrue(utils.is_exchange_information_valid({"kind": "PERPETUAL"}))
        self.assertFalse(utils.is_exchange_information_valid({"kind": "FUTURE"}))

    def test_config_keys(self):
        self.assertEqual("grvt_perpetual", utils.KEYS.connector)
        self.assertEqual("grvt_perpetual_testnet", utils.OTHER_DOMAINS_KEYS["grvt_perpetual_testnet"].connector)

    def test_default_fees(self):
        self.assertEqual(Decimal("0.0002"), utils.DEFAULT_FEES.maker_percent_fee_decimal)
        self.assertEqual(Decimal("0.0005"), utils.DEFAULT_FEES.taker_percent_fee_decimal)
