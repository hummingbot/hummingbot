import unittest

from hummingbot.connector.exchange.backpack import backpack_utils as utils


class BackpackUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"

    def test_is_exchange_information_valid(self):
        invalid_info_1 = {
            "visible": False,
            "marketType": "MARGIN",
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_1))

        invalid_info_2 = {
            "visible": False,
            "marketType": "SPOT",
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_2))

        invalid_info_3 = {
            "visible": True,
            "marketType": "MARGIN",
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_3))

        valid_info = {
            "visible": True,
            "marketType": "SPOT",
        }

        self.assertTrue(utils.is_exchange_information_valid(valid_info))
