import unittest

from hummingbot.connector.exchange.foxbit import foxbit_utils as utils


class FoxbitUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def test_is_exchange_information_valid(self):
        valid_info = {
            "status": "TRADING",
            "permissions": ["SPOT"],
        }

        self.assertTrue(utils.is_exchange_information_valid(valid_info))
