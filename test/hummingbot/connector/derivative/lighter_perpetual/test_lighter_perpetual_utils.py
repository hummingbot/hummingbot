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
            lighter_perpetual_api_key_index="4",
            lighter_perpetual_account_index="693751",
            lighter_perpetual_api_key_public_key="0x" + ("b" * 40),
            lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
        )

        self.assertEqual("lighter_perpetual", config.connector)
        self.assertEqual("4", config.lighter_perpetual_api_key_index.get_secret_value())
        self.assertEqual("693751", config.lighter_perpetual_account_index.get_secret_value())
        self.assertEqual("0x" + ("b" * 40), config.lighter_perpetual_api_key_public_key.get_secret_value())
        self.assertEqual("0x" + ("a" * 64), config.lighter_perpetual_api_key_private_key.get_secret_value())

    def test_api_key_index_must_be_integer(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualConfigMap(
                lighter_perpetual_api_key_index="not-an-integer",
                lighter_perpetual_account_index="693751",
                lighter_perpetual_api_key_public_key="0x" + ("b" * 40),
                lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
            )
        self.assertIn("API key index must be an integer", str(ctx.exception))

    def test_account_index_must_be_integer(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualConfigMap(
                lighter_perpetual_api_key_index="4",
                lighter_perpetual_account_index="not-an-integer",
                lighter_perpetual_api_key_public_key="0x" + ("b" * 40),
                lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
            )
        self.assertIn("account index must be an integer", str(ctx.exception))

    def test_mainnet_api_key_must_be_hex(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualConfigMap(
                lighter_perpetual_api_key_index="4",
                lighter_perpetual_account_index="693751",
                lighter_perpetual_api_key_public_key="0x" + ("b" * 40),
                lighter_perpetual_api_key_private_key="not-hex",
            )
        self.assertIn("hex string", str(ctx.exception))

    def test_testnet_api_key_must_be_hex(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualTestnetConfigMap(
                lighter_perpetual_testnet_api_key_index="4",
                lighter_perpetual_testnet_account_index="693751",
                lighter_perpetual_testnet_api_key_public_key="0x" + ("b" * 40),
                lighter_perpetual_testnet_api_key_private_key="not-hex",
            )
        self.assertIn("hex string", str(ctx.exception))

    def test_testnet_metadata_is_defined(self):
        self.assertIn("lighter_perpetual_testnet", utils.OTHER_DOMAINS)
        self.assertEqual("lighter_perpetual_testnet", utils.OTHER_DOMAINS_PARAMETER["lighter_perpetual_testnet"])
        self.assertEqual("BTC-USDC", utils.OTHER_DOMAINS_EXAMPLE_PAIR["lighter_perpetual_testnet"])
        self.assertEqual([0.00015, 0.0004], utils.OTHER_DOMAINS_DEFAULT_FEES["lighter_perpetual_testnet"])

    def test_connect_flow_prompts_for_api_key_instead_of_private_key(self):
        mainnet_key_index = utils.LighterPerpetualConfigMap.model_fields["lighter_perpetual_api_key_index"].json_schema_extra
        testnet_key_index = utils.LighterPerpetualTestnetConfigMap.model_fields["lighter_perpetual_testnet_api_key_index"].json_schema_extra

        self.assertTrue(mainnet_key_index["prompt_on_new"])
        self.assertIn("api key index", mainnet_key_index["prompt"].lower())

        self.assertTrue(testnet_key_index["prompt_on_new"])
        self.assertIn("api key index", testnet_key_index["prompt"].lower())

        # Verify the public key field is present and required
        mainnet_public = utils.LighterPerpetualConfigMap.model_fields["lighter_perpetual_api_key_public_key"].json_schema_extra
        self.assertTrue(mainnet_public["prompt_on_new"])
        self.assertIn("public key", mainnet_public["prompt"].lower())

        # Verify the private key field is separate and required
        mainnet_private = utils.LighterPerpetualConfigMap.model_fields["lighter_perpetual_api_key_private_key"].json_schema_extra
        self.assertTrue(mainnet_private["prompt_on_new"])
        self.assertIn("private key", mainnet_private["prompt"].lower())

        # Verify no (now-removed) EOA private key field is present
        self.assertNotIn("lighter_perpetual_private_key", utils.LighterPerpetualConfigMap.model_fields)
        self.assertNotIn("lighter_perpetual_testnet_private_key", utils.LighterPerpetualTestnetConfigMap.model_fields)
