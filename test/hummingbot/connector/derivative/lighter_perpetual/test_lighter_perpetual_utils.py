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
            lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
        )

        self.assertEqual("lighter_perpetual", config.connector)
        self.assertEqual("4", config.lighter_perpetual_api_key_index.get_secret_value())
        self.assertEqual("693751", config.lighter_perpetual_account_index.get_secret_value())
        self.assertEqual("0x" + ("a" * 64), config.lighter_perpetual_api_key_private_key.get_secret_value())

    def test_api_key_index_must_be_integer(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualConfigMap(
                lighter_perpetual_api_key_index="not-an-integer",
                lighter_perpetual_account_index="693751",
                lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
            )
        self.assertIn("API key index must be an integer", str(ctx.exception))

    def test_account_index_must_be_integer(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualConfigMap(
                lighter_perpetual_api_key_index="4",
                lighter_perpetual_account_index="not-an-integer",
                lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
            )
        self.assertIn("account index must be an integer", str(ctx.exception))

    def test_mainnet_api_key_must_be_hex(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualConfigMap(
                lighter_perpetual_api_key_index="4",
                lighter_perpetual_account_index="693751",
                lighter_perpetual_api_key_private_key="not-hex",
            )
        self.assertIn("hex string", str(ctx.exception))

    def test_testnet_api_key_must_be_hex(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualTestnetConfigMap(
                lighter_perpetual_testnet_api_key_index="4",
                lighter_perpetual_testnet_account_index="693751",
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

        # Verify the private key field is separate and required
        mainnet_private = utils.LighterPerpetualConfigMap.model_fields["lighter_perpetual_api_key_private_key"].json_schema_extra
        self.assertTrue(mainnet_private["prompt_on_new"])
        self.assertIn("private key", mainnet_private["prompt"].lower())

        # Verify no public key field is present (removed — account index is used instead)
        self.assertNotIn("lighter_perpetual_api_key_public_key", utils.LighterPerpetualConfigMap.model_fields)
        self.assertNotIn("lighter_perpetual_testnet_api_key_public_key", utils.LighterPerpetualTestnetConfigMap.model_fields)

        # Verify no (now-removed) EOA private key field is present
        self.assertNotIn("lighter_perpetual_private_key", utils.LighterPerpetualConfigMap.model_fields)
        self.assertNotIn("lighter_perpetual_testnet_private_key", utils.LighterPerpetualTestnetConfigMap.model_fields)

    # ------------------------------------------------------------------ #
    # Additional tests to cover early-return branches in validators        #
    # ------------------------------------------------------------------ #

    def test_mainnet_api_key_index_empty_string_accepted(self):
        """Empty string bypasses validation — used for unfilled config fields."""
        config = utils.LighterPerpetualConfigMap(
            lighter_perpetual_api_key_index="",
            lighter_perpetual_account_index="693751",
            lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
        )
        self.assertEqual("", config.lighter_perpetual_api_key_index.get_secret_value())

    def test_mainnet_account_index_empty_string_accepted(self):
        config = utils.LighterPerpetualConfigMap(
            lighter_perpetual_api_key_index="4",
            lighter_perpetual_account_index="",
            lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
        )
        self.assertEqual("", config.lighter_perpetual_account_index.get_secret_value())

    def test_mainnet_api_key_index_encrypted_blob_accepted(self):
        """An encrypted-blob string (>64 hex chars) should pass through validation unchanged."""
        encrypted = "a" * 66  # >64 characters, all hex → treated as encrypted blob
        config = utils.LighterPerpetualConfigMap(
            lighter_perpetual_api_key_index=encrypted,
            lighter_perpetual_account_index="693751",
            lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
        )
        self.assertEqual(encrypted, config.lighter_perpetual_api_key_index.get_secret_value())

    def test_mainnet_account_index_encrypted_blob_accepted(self):
        encrypted = "b" * 68
        config = utils.LighterPerpetualConfigMap(
            lighter_perpetual_api_key_index="4",
            lighter_perpetual_account_index=encrypted,
            lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
        )
        self.assertEqual(encrypted, config.lighter_perpetual_account_index.get_secret_value())

    def test_mainnet_private_key_encrypted_blob_accepted(self):
        encrypted = "c" * 100  # >64 hex chars → encrypted blob
        config = utils.LighterPerpetualConfigMap(
            lighter_perpetual_api_key_index="4",
            lighter_perpetual_account_index="693751",
            lighter_perpetual_api_key_private_key=encrypted,
        )
        self.assertEqual(encrypted, config.lighter_perpetual_api_key_private_key.get_secret_value())

    def test_testnet_api_key_index_empty_string_accepted(self):
        config = utils.LighterPerpetualTestnetConfigMap(
            lighter_perpetual_testnet_api_key_index="",
            lighter_perpetual_testnet_account_index="693751",
            lighter_perpetual_testnet_api_key_private_key="0x" + ("a" * 64),
        )
        self.assertEqual("", config.lighter_perpetual_testnet_api_key_index.get_secret_value())

    def test_testnet_account_index_empty_string_accepted(self):
        config = utils.LighterPerpetualTestnetConfigMap(
            lighter_perpetual_testnet_api_key_index="4",
            lighter_perpetual_testnet_account_index="",
            lighter_perpetual_testnet_api_key_private_key="0x" + ("a" * 64),
        )
        self.assertEqual("", config.lighter_perpetual_testnet_account_index.get_secret_value())

    def test_testnet_api_key_index_encrypted_blob_accepted(self):
        encrypted = "d" * 66
        config = utils.LighterPerpetualTestnetConfigMap(
            lighter_perpetual_testnet_api_key_index=encrypted,
            lighter_perpetual_testnet_account_index="693751",
            lighter_perpetual_testnet_api_key_private_key="0x" + ("a" * 64),
        )
        self.assertEqual(encrypted, config.lighter_perpetual_testnet_api_key_index.get_secret_value())

    def test_testnet_account_index_encrypted_blob_accepted(self):
        encrypted = "e" * 68
        config = utils.LighterPerpetualTestnetConfigMap(
            lighter_perpetual_testnet_api_key_index="4",
            lighter_perpetual_testnet_account_index=encrypted,
            lighter_perpetual_testnet_api_key_private_key="0x" + ("a" * 64),
        )
        self.assertEqual(encrypted, config.lighter_perpetual_testnet_account_index.get_secret_value())

    def test_testnet_private_key_encrypted_blob_accepted(self):
        encrypted = "f" * 100
        config = utils.LighterPerpetualTestnetConfigMap(
            lighter_perpetual_testnet_api_key_index="4",
            lighter_perpetual_testnet_account_index="693751",
            lighter_perpetual_testnet_api_key_private_key=encrypted,
        )
        self.assertEqual(encrypted, config.lighter_perpetual_testnet_api_key_private_key.get_secret_value())

    def test_testnet_api_key_index_must_be_integer(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualTestnetConfigMap(
                lighter_perpetual_testnet_api_key_index="not-an-integer",
                lighter_perpetual_testnet_account_index="693751",
                lighter_perpetual_testnet_api_key_private_key="0x" + ("a" * 64),
            )
        self.assertIn("integer", str(ctx.exception))

    def test_testnet_account_index_must_be_integer(self):
        with self.assertRaises(ValidationError) as ctx:
            utils.LighterPerpetualTestnetConfigMap(
                lighter_perpetual_testnet_api_key_index="4",
                lighter_perpetual_testnet_account_index="not-an-integer",
                lighter_perpetual_testnet_api_key_private_key="0x" + ("a" * 64),
            )
        self.assertIn("integer", str(ctx.exception))

    # ------------------------------------------------------------------ #
    # Branch coverage for migrate_legacy_fields non-dict paths            #
    # ------------------------------------------------------------------ #

    def test_mainnet_migrate_legacy_fields_with_non_dict_is_returned_unchanged(self):
        """migrate_legacy_fields must return non-dict data unchanged (covers line 130)."""
        result = utils.LighterPerpetualConfigMap.migrate_legacy_fields("not-a-dict")
        self.assertEqual("not-a-dict", result)

    def test_testnet_migrate_legacy_fields_with_non_dict_is_returned_unchanged(self):
        """testnet migrate_legacy_fields must return non-dict data unchanged (covers line 241)."""
        result = utils.LighterPerpetualTestnetConfigMap.migrate_legacy_fields("not-a-dict")
        self.assertEqual("not-a-dict", result)

    def test_mainnet_private_key_empty_string_accepted(self):
        """Empty private key returns early (line 115: return v when raw == '')."""
        config = utils.LighterPerpetualConfigMap(
            lighter_perpetual_api_key_index="4",
            lighter_perpetual_account_index="693751",
            lighter_perpetual_api_key_private_key="",
        )
        self.assertEqual("", config.lighter_perpetual_api_key_private_key.get_secret_value())

    def test_testnet_private_key_empty_string_accepted(self):
        """Empty testnet private key returns early (line 250: return v when raw == '')."""
        config = utils.LighterPerpetualTestnetConfigMap(
            lighter_perpetual_testnet_api_key_index="4",
            lighter_perpetual_testnet_account_index="693751",
            lighter_perpetual_testnet_api_key_private_key="",
        )
        self.assertEqual("", config.lighter_perpetual_testnet_api_key_private_key.get_secret_value())
