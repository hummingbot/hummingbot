import unittest

from hummingbot.connector.exchange.woo_x import woo_x_utils as utils


class WooXUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def test_is_exchange_information_valid(self):
        invalid_info_1 = {
            "symbol": "MARGIN_BTC_USDT",
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_1))

        invalid_info_2 = {
            "symbol": "PERP_BTC_ETH",
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_2))

        invalid_info_3 = {
            "symbol": "BTC-USDT",
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_3))

        valid_info_4 = {
            "symbol": f"SPOT_{self.base_asset}_{self.quote_asset}",
        }

        self.assertTrue(utils.is_exchange_information_valid(valid_info_4))
