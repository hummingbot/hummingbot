import unittest

from hummingbot.connector.exchange.gemini.gemini_utils import (
    CENTRALIZED,
    DEFAULT_FEES,
    EXAMPLE_PAIR,
    KEYS,
    is_exchange_information_valid,
)


class TestGeminiUtils(unittest.TestCase):

    def test_centralized_flag(self):
        self.assertTrue(CENTRALIZED)

    def test_example_pair(self):
        self.assertEqual("BTC-USD", EXAMPLE_PAIR)

    def test_default_fees(self):
        from decimal import Decimal
        self.assertEqual(Decimal("0.001"), DEFAULT_FEES.maker_percent_fee_decimal)
        self.assertEqual(Decimal("0.0035"), DEFAULT_FEES.taker_percent_fee_decimal)

    def test_keys_is_config_map(self):
        self.assertIsNotNone(KEYS)

    def test_is_exchange_information_valid_open(self):
        self.assertTrue(is_exchange_information_valid({"status": "open"}))

    def test_is_exchange_information_valid_closed(self):
        self.assertFalse(is_exchange_information_valid({"status": "closed"}))

    def test_is_exchange_information_valid_missing_status(self):
        self.assertFalse(is_exchange_information_valid({}))

    def test_is_exchange_information_valid_other_status(self):
        self.assertFalse(is_exchange_information_valid({"status": "halted"}))
