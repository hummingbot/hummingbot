import asyncio
from unittest import TestCase

import hummingbot.strategy.twap.twap_config_map as twap_config_map_module


class TwapConfigMapTests(TestCase):

    def test_string_to_boolean_conversion(self):
        true_variants = ["Yes", "YES", "yes", "y", "Y",
                         "true", "True", "TRUE", "t", "T",
                         "1"]
        for variant in true_variants:
            self.assertTrue(twap_config_map_module.str2bool(variant))

        false_variants = ["No", "NO", "no", "n", "N",
                          "false", "False", "FALSE", "f", "F",
                          "0"]
        for variant in false_variants:
            self.assertFalse(twap_config_map_module.str2bool(variant))

    def test_trading_pair_prompt(self):
        twap_config_map_module.twap_config_map.get("connector").value = "binance"
        self.assertEqual(twap_config_map_module.trading_pair_prompt(),
                         "Enter the token trading pair you would like to trade on binance (e.g. ZRX-ETH) >>> ")

        twap_config_map_module.twap_config_map.get("connector").value = "undefined-exchange"
        self.assertEqual(twap_config_map_module.trading_pair_prompt(),
                         "Enter the token trading pair you would like to trade on undefined-exchange >>> ")

    def test_trading_pair_validation(self):
        twap_config_map_module.twap_config_map.get("connector").value = "binance"
        self.assertIsNone(twap_config_map_module.validate_market_trading_pair_tuple("BTC-USDT"))

    def test_target_asset_amount_prompt(self):
        twap_config_map_module.twap_config_map.get("trading_pair").value = "BTC-USDT"
        twap_config_map_module.twap_config_map.get("trade_side").value = "buy"
        self.assertEqual(twap_config_map_module.target_asset_amount_prompt(),
                         "What is the total amount of BTC to be traded? (Default is 1.0) >>> ")

        twap_config_map_module.twap_config_map.get("trade_side").value = "sell"
        self.assertEqual(twap_config_map_module.target_asset_amount_prompt(),
                         "What is the total amount of BTC to be traded? (Default is 1.0) >>> ")

    def test_trade_side_config(self):
        config_var = twap_config_map_module.twap_config_map.get("trade_side")

        self.assertTrue(config_var.required)

        prompt_text = asyncio.get_event_loop().run_until_complete(config_var.get_prompt())
        self.assertEqual(prompt_text, "What operation will be executed? (buy/sell) >>> ")

    def test_trade_side_only_accepts_buy_or_sell(self):
        config_var = twap_config_map_module.twap_config_map.get("trade_side")

        validate_result = asyncio.get_event_loop().run_until_complete(config_var.validate("invalid value"))
        self.assertEqual(validate_result, "Invalid operation type.")

        validate_result = asyncio.get_event_loop().run_until_complete(config_var.validate("buy"))
        self.assertIsNone(validate_result)

        validate_result = asyncio.get_event_loop().run_until_complete(config_var.validate("sell"))
        self.assertIsNone(validate_result)
