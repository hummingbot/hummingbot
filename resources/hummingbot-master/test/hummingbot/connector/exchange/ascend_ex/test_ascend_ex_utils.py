import unittest

from hummingbot.connector.exchange.ascend_ex import ascend_ex_utils as utils


class AscendExUtilTestCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def test_is_pair_information_valid(self):
        invalid_info_1 = {
            "statusCode": None,
        }

        self.assertFalse(utils.is_pair_information_valid(invalid_info_1))

        invalid_info_2 = {
            "statusCode": "",
        }

        self.assertFalse(utils.is_pair_information_valid(invalid_info_2))

        invalid_info_3 = {
            "statusCode": "Err",
        }

        self.assertFalse(utils.is_pair_information_valid(invalid_info_3))

        invalid_info_4 = {
            "statusCode": "Normal",
        }

        self.assertTrue(utils.is_pair_information_valid(invalid_info_4))
