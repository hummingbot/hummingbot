from unittest import TestCase

from hummingbot.connector.exchange.lighter import lighter_utils as utils


class LighterUtilsTests(TestCase):
    def test_validate_non_negative_int_allows_blank_index(self):
        self.assertIsNone(utils.validate_non_negative_int(""))
        self.assertIsNone(utils.validate_non_negative_int(None))

    def test_validate_non_negative_int_raises_for_negative(self):
        with self.assertRaises(ValueError):
            utils.validate_non_negative_int(-1)

    def test_mainnet_config_map_uses_l1_address_with_optional_index(self):
        config = utils.LighterConfigMap(
            lighter_l1_address="0xabc",
            lighter_api_key_index="8",
            lighter_api_private_key="0xprivate",
        )

        self.assertEqual("0xabc", config.lighter_l1_address)
        self.assertIsNone(config.lighter_account_index)
        self.assertEqual(8, config.lighter_api_key_index)

    def test_testnet_config_map_accepts_index_override(self):
        config = utils.LighterTestnetConfigMap(
            lighter_testnet_l1_address="0xabc",
            lighter_testnet_account_index="12",
            lighter_testnet_api_key_index="8",
            lighter_testnet_api_private_key="0xprivate",
        )

        self.assertEqual(12, config.lighter_testnet_account_index)
        self.assertEqual(8, config.lighter_testnet_api_key_index)
