import unittest
from decimal import Decimal

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', '..'))

from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_utils import (
    CENTRALIZED,
    EXAMPLE_PAIR,
    DEFAULT_FEES,
    is_exchange_information_valid,
    ArchitectPerpetualConfigMap,
)


class TestArchitectPerpetualUtils(unittest.TestCase):

    def test_centralized(self):
        self.assertTrue(CENTRALIZED)

    def test_example_pair(self):
        self.assertEqual(EXAMPLE_PAIR, "ES-USD")

    def test_default_fees(self):
        self.assertEqual(DEFAULT_FEES.maker_percent_fee_decimal, Decimal("0.0002"))
        self.assertEqual(DEFAULT_FEES.taker_percent_fee_decimal, Decimal("0.0005"))

    def test_is_exchange_information_valid_with_data(self):
        exchange_info = {"symbol": "ES-USD", "price": "100.0"}
        self.assertTrue(is_exchange_information_valid(exchange_info))

    def test_is_exchange_information_valid_with_empty(self):
        self.assertFalse(is_exchange_information_valid({}))

    def test_is_exchange_information_valid_with_none(self):
        self.assertFalse(is_exchange_information_valid(None))

    def test_config_map_connector_name(self):
        config = ArchitectPerpetualConfigMap.construct()
        self.assertEqual(config.connector, "architect_perpetual")


if __name__ == "__main__":
    unittest.main()
