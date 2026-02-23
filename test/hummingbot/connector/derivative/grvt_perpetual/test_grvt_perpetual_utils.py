from unittest import TestCase

from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_utils import (
    GrvtPerpetualConfigMap,
    GrvtPerpetualTestnetConfigMap,
    grvt_instrument_to_hb_trading_pair,
    hb_trading_pair_to_grvt_instrument,
    is_exchange_information_valid,
)


class GrvtPerpetualUtilsTests(TestCase):
    def test_hb_trading_pair_to_grvt_instrument(self):
        result = hb_trading_pair_to_grvt_instrument("BTC-USDT")
        self.assertEqual("BTC_USDT_Perp", result)

    def test_hb_trading_pair_to_grvt_instrument_eth(self):
        result = hb_trading_pair_to_grvt_instrument("ETH-USDT")
        self.assertEqual("ETH_USDT_Perp", result)

    def test_grvt_instrument_to_hb_trading_pair(self):
        result = grvt_instrument_to_hb_trading_pair("BTC_USDT_Perp")
        self.assertEqual("BTC-USDT", result)

    def test_grvt_instrument_to_hb_trading_pair_eth(self):
        result = grvt_instrument_to_hb_trading_pair("ETH_USDT_Perp")
        self.assertEqual("ETH-USDT", result)

    def test_roundtrip_conversion(self):
        original = "BTC-USDT"
        instrument = hb_trading_pair_to_grvt_instrument(original)
        roundtripped = grvt_instrument_to_hb_trading_pair(instrument)
        self.assertEqual(original, roundtripped)

    def test_grvt_instrument_to_hb_invalid_format(self):
        # Single-part instrument should pass through
        result = grvt_instrument_to_hb_trading_pair("INVALID")
        self.assertEqual("INVALID", result)

    def test_is_exchange_information_valid_active(self):
        instrument = {"instrument": "BTC_USDT_Perp", "is_active": True}
        self.assertTrue(is_exchange_information_valid(instrument))

    def test_is_exchange_information_valid_inactive(self):
        instrument = {"instrument": "BTC_USDT_Perp", "is_active": False}
        self.assertFalse(is_exchange_information_valid(instrument))

    def test_is_exchange_information_valid_missing_field(self):
        # Should default to True if is_active is not present
        instrument = {"instrument": "BTC_USDT_Perp"}
        self.assertTrue(is_exchange_information_valid(instrument))

    def test_config_map_connector_name(self):
        config = GrvtPerpetualConfigMap.model_construct()
        self.assertEqual("grvt_perpetual", config.connector)

    def test_config_map_has_required_fields(self):
        # Ensure the config map has the expected fields
        fields = GrvtPerpetualConfigMap.model_fields
        self.assertIn("grvt_perpetual_api_key", fields)
        self.assertIn("grvt_perpetual_secret_key", fields)
        self.assertIn("grvt_perpetual_sub_account_id", fields)

    def test_testnet_config_map_connector_name(self):
        config = GrvtPerpetualTestnetConfigMap.model_construct()
        self.assertEqual("grvt_perpetual_testnet", config.connector)

    def test_testnet_config_map_has_required_fields(self):
        fields = GrvtPerpetualTestnetConfigMap.model_fields
        self.assertIn("grvt_perpetual_testnet_api_key", fields)
        self.assertIn("grvt_perpetual_testnet_secret_key", fields)
        self.assertIn("grvt_perpetual_testnet_sub_account_id", fields)
