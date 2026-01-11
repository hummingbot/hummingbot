import unittest
from decimal import Decimal

from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_utils import (
    CENTRALIZED,
    DEFAULT_FEES,
    EXAMPLE_PAIR,
    AevoPerpetualConfigMap,
)


class AevoPerpetualUtilsTests(unittest.TestCase):
    def test_centralized_is_true(self):
        self.assertTrue(CENTRALIZED)

    def test_example_pair_format(self):
        self.assertEqual(EXAMPLE_PAIR, "ETH-PERP")

    def test_default_fees(self):
        self.assertEqual(DEFAULT_FEES.maker_percent_fee_decimal, Decimal("0.0002"))
        self.assertEqual(DEFAULT_FEES.taker_percent_fee_decimal, Decimal("0.0005"))

    def test_config_map_connector_name(self):
        config = AevoPerpetualConfigMap.model_construct()
        self.assertEqual(config.connector, "aevo_perpetual")
