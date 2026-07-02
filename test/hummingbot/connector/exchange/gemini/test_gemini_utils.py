from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.gemini.gemini_constants import convert_timestamp_to_seconds
from hummingbot.connector.exchange.gemini.gemini_utils import (
    CENTRALIZED,
    DEFAULT_FEES,
    EXAMPLE_PAIR,
    KEYS,
    GeminiConfigMap,
)


class GeminiUtilsTests(TestCase):

    def test_centralized_flag(self):
        self.assertTrue(CENTRALIZED)

    def test_example_pair(self):
        self.assertEqual("BTC-USD", EXAMPLE_PAIR)

    def test_default_fees(self):
        self.assertEqual(Decimal("0.002"), DEFAULT_FEES.maker_percent_fee_decimal)
        self.assertEqual(Decimal("0.004"), DEFAULT_FEES.taker_percent_fee_decimal)
        self.assertTrue(DEFAULT_FEES.buy_percent_fee_deducted_from_returns)

    def test_keys_config_map(self):
        self.assertIsInstance(KEYS, GeminiConfigMap)
        self.assertEqual("gemini", KEYS.connector)

    def test_config_map_has_api_key_fields(self):
        fields = GeminiConfigMap.model_fields
        self.assertIn("gemini_api_key", fields)
        self.assertIn("gemini_api_secret", fields)

    def test_convert_timestamp_to_seconds(self):
        # Nanoseconds (> 1e15) -> seconds
        self.assertAlmostEqual(1700000000.0, convert_timestamp_to_seconds(1_700_000_000_000_000_000))
        # Milliseconds (> 1e11) -> seconds
        self.assertAlmostEqual(1700000000.0, convert_timestamp_to_seconds(1_700_000_000_000))
        # Already in seconds -> unchanged
        self.assertEqual(1700000000, convert_timestamp_to_seconds(1_700_000_000))
