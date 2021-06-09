from decimal import Decimal
from unittest import TestCase

from hummingbot.core.utils.fixed_rate_source import FixedRateSource


class FixedRateSourceTests(TestCase):

    def test_look_for_unconfigured_pair_rate(self):
        rate_source = FixedRateSource()
        self.assertIsNone(rate_source.rate("BTC-USDT"))

    def test_get_rate(self):
        rate_source = FixedRateSource()
        rate_source.add_rate("BTC-USDT", Decimal(40000))

        self.assertEqual(rate_source.rate("BTC-USDT"), Decimal(40000))

    def test_get_rate_when_inverted_pair_is_configured(self):
        rate_source = FixedRateSource()
        rate_source.add_rate("BTC-USDT", Decimal(40000))

        self.assertEqual(rate_source.rate("USDT-BTC"), Decimal(1) / Decimal(40000))

    def test_string_representation(self):
        self.assertEqual(str(FixedRateSource()), "fixed rates")
