import json
from unittest import TestCase

from pydantic import ValidationError

from hummingbot.connector.exchange.lighter.lighter_utils import (
    LighterConfigMap,
    LighterTestnetConfigMap,
    is_exchange_information_valid,
)


class LighterUtilsTests(TestCase):
    @staticmethod
    def _encrypted_secret_payload_hex() -> str:
        payload = {"crypto": {}, "version": 3, "alias": ""}
        return json.dumps(payload).encode("utf-8").hex()

    def test_config_map_title(self):
        self.assertEqual("lighter", LighterConfigMap.model_config.get("title"))

    def test_testnet_config_map_title(self):
        self.assertEqual("lighter_testnet", LighterTestnetConfigMap.model_config.get("title"))

    def test_connect_flow_prompts_for_api_key_instead_of_private_key(self):
        mainnet_api_key = LighterConfigMap.model_fields["lighter_api_key"].json_schema_extra
        mainnet_private_key = LighterConfigMap.model_fields["lighter_private_key"].json_schema_extra
        testnet_api_key = LighterTestnetConfigMap.model_fields["lighter_testnet_api_key"].json_schema_extra
        testnet_private_key = LighterTestnetConfigMap.model_fields["lighter_testnet_private_key"].json_schema_extra

        self.assertTrue(mainnet_api_key["prompt_on_new"])
        self.assertEqual("Enter your Lighter API key (hex string, e.g. 3d6e9253...4357)", mainnet_api_key["prompt"])
        self.assertFalse(mainnet_private_key["prompt_on_new"])

        self.assertTrue(testnet_api_key["prompt_on_new"])
        self.assertEqual("Enter your Lighter testnet API key", testnet_api_key["prompt"])
        self.assertFalse(testnet_private_key["prompt_on_new"])

    def test_is_exchange_information_valid(self):
        self.assertTrue(is_exchange_information_valid({"symbol": "ETH/USDC", "market_type": "spot", "status": "active"}))
        self.assertFalse(is_exchange_information_valid({"symbol": "ETH/USDC", "market_type": "perp", "status": "active"}))
        self.assertFalse(is_exchange_information_valid({"symbol": "ETH/USDC", "market_type": "spot", "status": "halted"}))
        self.assertFalse(is_exchange_information_valid({"market_type": "spot", "status": "active"}))

    def test_mainnet_config_validates_integer_indexes(self):
        cfg = LighterConfigMap(
            lighter_api_key="0x" + ("a" * 64),
            lighter_api_secret=" 123 ",
            lighter_account_index=" 456 ",
        )

        self.assertEqual("123", cfg.lighter_api_secret.get_secret_value())
        self.assertEqual("456", cfg.lighter_account_index.get_secret_value())

        with self.assertRaises(ValidationError):
            LighterConfigMap(
                lighter_api_key="0x" + ("a" * 64),
                lighter_api_secret="not-an-int",
                lighter_account_index="456",
            )

        cfg_empty = LighterConfigMap(
            lighter_api_key="0x" + ("a" * 64),
            lighter_api_secret="",
            lighter_account_index="",
        )
        self.assertEqual("", cfg_empty.lighter_api_secret.get_secret_value())
        self.assertEqual("", cfg_empty.lighter_account_index.get_secret_value())

    def test_testnet_config_validates_integer_indexes(self):
        cfg = LighterTestnetConfigMap(
            lighter_testnet_api_key="0x" + ("a" * 64),
            lighter_testnet_api_secret=" 7 ",
            lighter_testnet_account_index=" 890 ",
        )

        self.assertEqual("7", cfg.lighter_testnet_api_secret.get_secret_value())
        self.assertEqual("890", cfg.lighter_testnet_account_index.get_secret_value())

        cfg_empty = LighterTestnetConfigMap(
            lighter_testnet_api_key="0x" + ("a" * 64),
            lighter_testnet_api_secret="",
            lighter_testnet_account_index="",
        )
        self.assertEqual("", cfg_empty.lighter_testnet_api_secret.get_secret_value())
        self.assertEqual("", cfg_empty.lighter_testnet_account_index.get_secret_value())

        with self.assertRaises(ValidationError):
            LighterTestnetConfigMap(
                lighter_testnet_api_key="0x" + ("a" * 64),
                lighter_testnet_api_secret="7",
                lighter_testnet_account_index="abc",
            )

    def test_mainnet_config_validates_hex_api_key(self):
        hex_key = "0x" + ("a" * 64)
        cfg = LighterConfigMap(
            lighter_api_secret="123",
            lighter_account_index="456",
            lighter_api_key=hex_key,
        )
        self.assertEqual(hex_key, cfg.lighter_api_key.get_secret_value())

        with self.assertRaises(ValidationError):
            LighterConfigMap(
                lighter_api_secret="123",
                lighter_account_index="456",
                lighter_api_key="not-hex",
            )

    def test_testnet_config_validates_hex_api_key(self):
        hex_key = "0x" + ("a" * 64)
        cfg = LighterTestnetConfigMap(
            lighter_testnet_api_key=hex_key,
            lighter_testnet_api_secret="7",
            lighter_testnet_account_index="890",
        )
        self.assertEqual(hex_key, cfg.lighter_testnet_api_key.get_secret_value())

        with self.assertRaises(ValidationError):
            LighterTestnetConfigMap(
                lighter_testnet_api_key="not-hex",
                lighter_testnet_api_secret="7",
                lighter_testnet_account_index="890",
            )

    def test_mainnet_config_accepts_encrypted_index_values_before_decrypt(self):
        encrypted = self._encrypted_secret_payload_hex()
        cfg = LighterConfigMap(
            lighter_api_key=encrypted,
            lighter_api_secret=encrypted,
            lighter_account_index=encrypted,
        )

        self.assertEqual(encrypted, cfg.lighter_api_secret.get_secret_value())
        self.assertEqual(encrypted, cfg.lighter_account_index.get_secret_value())

    def test_testnet_config_accepts_encrypted_index_values_before_decrypt(self):
        encrypted = self._encrypted_secret_payload_hex()
        cfg = LighterTestnetConfigMap(
            lighter_testnet_api_key="0x" + ("a" * 64),
            lighter_testnet_api_secret=encrypted,
            lighter_testnet_account_index=encrypted,
        )

        self.assertEqual(encrypted, cfg.lighter_testnet_api_secret.get_secret_value())
        self.assertEqual(encrypted, cfg.lighter_testnet_account_index.get_secret_value())
