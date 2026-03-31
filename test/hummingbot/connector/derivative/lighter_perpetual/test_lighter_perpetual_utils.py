import unittest
from decimal import Decimal

from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_utils as utils


class LighterPerpetualUtilsTests(unittest.TestCase):
    def test_default_fees_match_observed_base_tier(self):
        self.assertEqual(Decimal("0.00015"), utils.DEFAULT_FEES.maker_percent_fee_decimal)
        self.assertEqual(Decimal("0.0004"), utils.DEFAULT_FEES.taker_percent_fee_decimal)

    def test_mainnet_config_aliases_and_connector_name(self):
        config = utils.LighterPerpetualConfigMap(
            lighter_perpetual_api_key="key",
            lighter_perpetual_api_secret="secret",
            lighter_perpetual_account_index="123",
        )

        self.assertEqual("lighter_perpetual", config.connector)
        self.assertEqual("key", config.lighter_perpetual_api_key.get_secret_value())
        self.assertEqual("secret", config.lighter_perpetual_api_secret.get_secret_value())
        self.assertEqual("123", config.lighter_perpetual_account_index.get_secret_value())

    def test_testnet_metadata_is_defined(self):
        self.assertIn("lighter_perpetual_testnet", utils.OTHER_DOMAINS)
        self.assertEqual("lighter_perpetual_testnet", utils.OTHER_DOMAINS_PARAMETER["lighter_perpetual_testnet"])
        self.assertEqual("BTC-USD", utils.OTHER_DOMAINS_EXAMPLE_PAIR["lighter_perpetual_testnet"])
        self.assertEqual([0.00015, 0.0004], utils.OTHER_DOMAINS_DEFAULT_FEES["lighter_perpetual_testnet"])
