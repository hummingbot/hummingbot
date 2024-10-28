import unittest

from hummingbot.connector.exchange.dexalot import dexalot_utils as utils


class DexalotUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "AVAX"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"

    def test_is_exchange_information_valid(self):
        invalid_info_1 = {
            "allowswap": False,
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_1))

        invalid_info_4 = {
            "allowswap": True,
        }

        self.assertTrue(utils.is_exchange_information_valid(invalid_info_4))
