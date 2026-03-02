from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_utils import (
    ArchitectPerpetualConfigMap,
    DEFAULT_FEES,
    EXAMPLE_PAIR,
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    is_exchange_information_valid,
    split_trading_pair,
)


class ArchitectPerpetualUtilsTests(TestCase):
    def test_default_fees(self):
        self.assertEqual(DEFAULT_FEES.maker_percent_fee_decimal, Decimal("0.0002"))
        self.assertEqual(DEFAULT_FEES.taker_percent_fee_decimal, Decimal("0.0005"))
        self.assertFalse(DEFAULT_FEES.buy_percent_fee_deducted_from_returns)

    def test_example_pair(self):
        self.assertEqual(EXAMPLE_PAIR, "BTC-USD")

    def test_is_exchange_information_valid_with_valid_info(self):
        exchange_info = [{"symbol": "BTC-USD-PERP", "min_order_size": "0.001"}]
        self.assertTrue(is_exchange_information_valid(exchange_info))

    def test_is_exchange_information_valid_with_empty_info(self):
        self.assertFalse(is_exchange_information_valid([]))

    def test_is_exchange_information_valid_with_none(self):
        self.assertFalse(is_exchange_information_valid(None))

    def test_split_trading_pair_standard(self):
        base, quote = split_trading_pair("BTC-USD")
        self.assertEqual(base, "BTC")
        self.assertEqual(quote, "USD")

    def test_split_trading_pair_eth(self):
        base, quote = split_trading_pair("ETH-USD")
        self.assertEqual(base, "ETH")
        self.assertEqual(quote, "USD")

    def test_split_trading_pair_single_part(self):
        base, quote = split_trading_pair("BTCUSD")
        self.assertEqual(base, "BTCUSD")
        self.assertEqual(quote, "USD")

    def test_convert_from_exchange_trading_pair_perp_format(self):
        result = convert_from_exchange_trading_pair("BTC-USD-PERP")
        self.assertEqual(result, "BTC-USD")

    def test_convert_from_exchange_trading_pair_underscore_format(self):
        result = convert_from_exchange_trading_pair("BTC_USD")
        self.assertEqual(result, "BTC-USD")

    def test_convert_from_exchange_trading_pair_combined(self):
        result = convert_from_exchange_trading_pair("ETH_USD-PERP")
        self.assertEqual(result, "ETH-USD")

    def test_convert_to_exchange_trading_pair(self):
        result = convert_to_exchange_trading_pair("BTC-USD")
        self.assertEqual(result, "BTC-USD-PERP")

    def test_convert_to_exchange_trading_pair_eth(self):
        result = convert_to_exchange_trading_pair("ETH-USD")
        self.assertEqual(result, "ETH-USD-PERP")

    def test_convert_roundtrip(self):
        original = "SOL-USD"
        exchange_format = convert_to_exchange_trading_pair(original)
        back_to_hb = convert_from_exchange_trading_pair(exchange_format)
        self.assertEqual(back_to_hb, original)

    def test_config_map_has_api_key(self):
        config = ArchitectPerpetualConfigMap.construct()
        self.assertTrue(hasattr(config, 'architect_perpetual_api_key'))

    def test_config_map_has_api_secret(self):
        config = ArchitectPerpetualConfigMap.construct()
        self.assertTrue(hasattr(config, 'architect_perpetual_api_secret'))

    def test_config_map_connector_name(self):
        config = ArchitectPerpetualConfigMap.construct()
        self.assertEqual(config.connector, "architect_perpetual")
