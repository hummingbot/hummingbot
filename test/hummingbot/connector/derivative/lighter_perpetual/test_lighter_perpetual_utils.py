import unittest
from decimal import Decimal

from pydantic import ValidationError

from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_utils as utils


class LighterPerpetualUtilsTests(unittest.TestCase):
    def test_default_fees_match_observed_base_tier(self):
        self.assertEqual(Decimal("0.00015"), utils.DEFAULT_FEES.maker_percent_fee_decimal)
        self.assertEqual(Decimal("0.0004"), utils.DEFAULT_FEES.taker_percent_fee_decimal)

    def test_mainnet_config_aliases_and_connector_name(self):
        config = utils.LighterPerpetualConfigMap(
            lighter_perpetual_api_key="0x" + ("a" * 64),
            lighter_perpetual_api_secret="4",
            lighter_perpetual_account_index="693751",
        )

        self.assertEqual("lighter_perpetual", config.connector)
        self.assertEqual("0x" + ("a" * 64), config.lighter_perpetual_api_key.get_secret_value())
        self.assertEqual("4", config.lighter_perpetual_api_secret.get_secret_value())
        self.assertEqual("693751", config.lighter_perpetual_account_index.get_secret_value())

    def test_api_key_index_must_be_integer(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualConfigMap(
                lighter_perpetual_api_secret="not-an-integer",
                lighter_perpetual_account_index="693751",
            )
        self.assertIn("API key index must be an integer", str(ctx.exception))

    def test_account_index_must_be_integer(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualConfigMap(
                lighter_perpetual_api_secret="4",
                lighter_perpetual_account_index="not-an-integer",
            )
        self.assertIn("account index must be an integer", str(ctx.exception))

    def test_mainnet_api_key_must_be_hex(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualConfigMap(
                lighter_perpetual_api_key="not-hex",
                lighter_perpetual_api_secret="4",
                lighter_perpetual_account_index="693751",
            )
        self.assertIn("even-length hex string of at least 64", str(ctx.exception))

    def test_testnet_api_key_must_be_hex(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualTestnetConfigMap(
                lighter_perpetual_testnet_api_key="not-hex",
                lighter_perpetual_testnet_api_secret="4",
                lighter_perpetual_testnet_account_index="693751",
            )
        self.assertIn("even-length hex string of at least 64", str(ctx.exception))

    def test_testnet_metadata_is_defined(self):
        self.assertIn("lighter_perpetual_testnet", utils.OTHER_DOMAINS)
        self.assertEqual("lighter_perpetual_testnet", utils.OTHER_DOMAINS_PARAMETER["lighter_perpetual_testnet"])
        self.assertEqual("BTC-USDC", utils.OTHER_DOMAINS_EXAMPLE_PAIR["lighter_perpetual_testnet"])
        self.assertEqual([0.00015, 0.0004], utils.OTHER_DOMAINS_DEFAULT_FEES["lighter_perpetual_testnet"])

    def test_connect_flow_prompts_for_api_key_instead_of_private_key(self):
        mainnet_api_key = utils.LighterPerpetualConfigMap.model_fields["lighter_perpetual_api_key"].json_schema_extra
        mainnet_private_key = utils.LighterPerpetualConfigMap.model_fields["lighter_perpetual_private_key"].json_schema_extra
        testnet_api_key = utils.LighterPerpetualTestnetConfigMap.model_fields["lighter_perpetual_testnet_api_key"].json_schema_extra
        testnet_private_key = utils.LighterPerpetualTestnetConfigMap.model_fields["lighter_perpetual_testnet_private_key"].json_schema_extra

        self.assertTrue(mainnet_api_key["prompt_on_new"])
        self.assertEqual("Enter your Lighter API key (hex string, e.g. 3d6e9253...4357)", mainnet_api_key["prompt"])
        self.assertFalse(mainnet_private_key["prompt_on_new"])

        self.assertTrue(testnet_api_key["prompt_on_new"])
        self.assertEqual("Enter your Lighter testnet API key", testnet_api_key["prompt"])
        self.assertFalse(testnet_private_key["prompt_on_new"])
