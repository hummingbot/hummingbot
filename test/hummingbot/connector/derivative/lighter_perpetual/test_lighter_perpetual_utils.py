from unittest import TestCase

from hummingbot.connector.derivative.lighter_perpetual import (
    lighter_perpetual_api_utils as api_utils,
    lighter_perpetual_utils as utils,
)


class LighterPerpetualUtilsTests(TestCase):
    def test_validate_non_negative_int(self):
        self.assertEqual(7, utils.validate_non_negative_int("7"))
        self.assertIsNone(utils.validate_non_negative_int(""))

    def test_validate_non_negative_int_raises_for_negative(self):
        with self.assertRaises(ValueError):
            utils.validate_non_negative_int(-1)

    def test_mainnet_config_map_uses_l1_address_without_account_index(self):
        config = utils.LighterPerpetualConfigMap(
            lighter_perpetual_l1_address="0xabc",
            lighter_perpetual_api_key_index="8",
            lighter_perpetual_api_private_key="0xabc",
        )

        self.assertEqual("0xabc", config.lighter_perpetual_l1_address)
        self.assertFalse(hasattr(config, "lighter_perpetual_account_index"))
        self.assertEqual(8, config.lighter_perpetual_api_key_index)

    def test_testnet_config_map_uses_l1_address_without_account_index(self):
        config = utils.LighterPerpetualTestnetConfigMap(
            lighter_perpetual_testnet_l1_address="0xabc",
            lighter_perpetual_testnet_api_key_index="1",
            lighter_perpetual_testnet_api_private_key="0xdef",
        )

        self.assertEqual("0xabc", config.lighter_perpetual_testnet_l1_address)
        self.assertFalse(hasattr(config, "lighter_perpetual_testnet_account_index"))
        self.assertEqual(1, config.lighter_perpetual_testnet_api_key_index)

    def test_other_domains_settings_include_testnet(self):
        self.assertIn("lighter_perpetual_testnet", utils.OTHER_DOMAINS)
        self.assertIn("lighter_perpetual_testnet", utils.OTHER_DOMAINS_DEFAULT_FEES)

    def test_extract_account_snapshot_by_l1_address_from_sub_accounts_response(self):
        response = {
            "code": 200,
            "l1_address": "0xe34167D92340c95A7775495d78bcc3Dc21cf11c0",
            "sub_accounts": [
                {
                    "code": 0,
                    "account_type": 0,
                    "index": 724450,
                    "l1_address": "0xe34167D92340c95A7775495d78bcc3Dc21cf11c0",
                    "available_balance": "",
                    "collateral": "50.000000",
                }
            ],
        }

        account = api_utils.extract_account_snapshot(
            response, l1_address="0xe34167D92340c95A7775495d78bcc3Dc21cf11c0"
        )

        self.assertEqual(724450, api_utils.account_index_from_account(account))
