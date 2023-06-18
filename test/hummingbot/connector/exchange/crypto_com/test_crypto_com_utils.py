import unittest

from hummingbot.connector.exchange.crypto_com import crypto_com_utils as utils


class CryptoComUtilTestCases(unittest.TestCase):

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
            "tradable": False,
            "inst_type": "PERPETUAL_SWAP",
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_1))

        invalid_info_2 = {
            "tradable": False,
            "inst_type": "CCY_PAIR",
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_2))

        invalid_info_3 = {
            "tradable": True,
            "inst_type": "PERPETUAL_SWAP",
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_3))

        invalid_info_4 = {
            "tradable": True,
            "inst_type": "CCY_PAIR",
        }

        self.assertTrue(utils.is_exchange_information_valid(invalid_info_4))
