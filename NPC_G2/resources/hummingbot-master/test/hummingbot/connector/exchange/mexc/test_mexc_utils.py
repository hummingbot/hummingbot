import unittest

from hummingbot.connector.exchange.mexc import mexc_utils as utils


class MexcUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def test_is_exchange_information_valid(self):
        invalid_info_1 = {
            "status": "BREAK",
            "permissions": ["MARGIN"],
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_1))

        invalid_info_2 = {
            "status": "BREAK",
            "permissions": ["SPOT"],
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_2))

        invalid_info_3 = {
            "status": "1",
            "permissions": ["MARGIN"],
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_3))

        invalid_info_4 = {
            "status": "1",
            "permissions": ["SPOT"],
        }

        self.assertTrue(utils.is_exchange_information_valid(invalid_info_4))
