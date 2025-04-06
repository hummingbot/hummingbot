import asyncio
from unittest import TestCase
from decimal import Decimal

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

    def test_order_delay_default(self):
        twap_config_map_module.twap_config_map.get("start_datetime").value = "2021-10-01 00:00:00"
        twap_config_map_module.twap_config_map.get("end_datetime").value = "2021-10-02 00:00:00"
        twap_config_map_module.twap_config_map.get("target_asset_amount").value = Decimal("1.0")
        twap_config_map_module.twap_config_map.get("order_step_size").value = Decimal("1.0")

        twap_config_map_module.set_order_delay_default()

        self.assertEqual(twap_config_map_module.twap_config_map.get("order_delay_time").default, 86400.0)

    def test_order_step_size(self):
        # Test order_step_size with a non-decimal value
        text = twap_config_map_module.validate_order_step_size("a!")
        self.assertEqual(text, "a! is not in decimal format.")

        # Test order_step_size below zero value
        negative_value = twap_config_map_module.validate_order_step_size("-1")
        self.assertEqual(negative_value, "Value must be more than 0.")

        # Test order_step_size value greater than target_asset_amount
        twap_config_map_module.twap_config_map.get("target_asset_amount").value = Decimal("1.0")
        validate_order_step_size = twap_config_map_module.validate_order_step_size("1.1")
        self.assertEqual(validate_order_step_size,
                         "Order step size cannot be greater than the total trade amount.")
