from unittest import TestCase

from hummingbot.connector.exchange.ndax import ndax_utils as utils


class NdaxUtilsTests(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def test_is_exchange_information_validity(self):
        valid_info_1 = {
            "SessionStatus": "Running",
        }

        self.assertTrue(utils.is_exchange_information_valid(valid_info_1))

        invalid_info_2 = {
            "SessionStatus": "Stopped",
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_2))

        invalid_info_3 = {
            "Status": "Running",
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_3))
