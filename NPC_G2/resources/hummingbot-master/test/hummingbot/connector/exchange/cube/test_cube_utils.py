import unittest
from unittest.mock import Mock

from hummingbot.connector.exchange.cube import cube_utils as utils


class CubeUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "SOL"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def test_is_exchange_information_valid(self):
        invalid_info_0 = {
            "disabled": False,
            "status": 1
        }

        self.assertTrue(utils.is_exchange_information_valid(invalid_info_0))

        invalid_info_1 = {
            "disabled": False,
            "status": 2
        }

        self.assertTrue(utils.is_exchange_information_valid(invalid_info_1))

        invalid_info_2 = {
            "disabled": True,
            "status": 1
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_2))

        invalid_info_3 = {
            "disabled": False,
            "status": 3
        }

        self.assertFalse(utils.is_exchange_information_valid(invalid_info_3))

    def test_raw_units_to_number(self):
        # Create a mock RawUnits object
        raw_units = Mock()
        raw_units.word0 = 1
        raw_units.word1 = 2
        raw_units.word2 = 3
        raw_units.word3 = 4

        # Call the function with the mock object
        result = utils.raw_units_to_number(raw_units)

        # Calculate the expected result
        expected_result = raw_units.word0 + (raw_units.word1 << 64) + (raw_units.word2 << 128) + (
            raw_units.word3 << 192)

        # Assert that the function returned the expected result
        self.assertEqual(result, expected_result)
