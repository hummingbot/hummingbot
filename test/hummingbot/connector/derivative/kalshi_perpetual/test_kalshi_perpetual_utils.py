from decimal import Decimal
from unittest import TestCase

from pydantic import SecretStr

import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_utils as utils
from hummingbot.client.settings import AllConnectorSettings, ConnectorType


class KalshiPerpetualUtilsTests(TestCase):

    def test_default_fees_are_base_tier_decimal_fractions(self):
        self.assertEqual(Decimal("0.0005"), utils.DEFAULT_FEES.maker_percent_fee_decimal)
        self.assertEqual(Decimal("0.0012"), utils.DEFAULT_FEES.taker_percent_fee_decimal)
        self.assertFalse(utils.DEFAULT_FEES.buy_percent_fee_deducted_from_returns)
        self.assertEqual("USD", utils.DEFAULT_FEES.percent_fee_token)

    def test_config_map_credential_fields_are_secure_connect_keys(self):
        self.assertEqual("kalshi_perpetual", utils.KEYS.connector)
        for field_name in ("kalshi_perpetual_api_key", "kalshi_perpetual_private_key"):
            extra = utils.KalshiPerpetualConfigMap.model_fields[field_name].json_schema_extra
            self.assertTrue(extra["is_secure"], field_name)
            self.assertTrue(extra["is_connect_key"], field_name)
            self.assertTrue(extra["prompt_on_new"], field_name)

    def test_config_map_holds_credentials_as_secrets(self):
        # Constructing the map runs the `connector` validator, which only accepts registered connectors.
        config = utils.KalshiPerpetualConfigMap(
            kalshi_perpetual_api_key="key-id",
            kalshi_perpetual_private_key="private-key",
        )

        self.assertIsInstance(config.kalshi_perpetual_api_key, SecretStr)
        self.assertIsInstance(config.kalshi_perpetual_private_key, SecretStr)
        self.assertEqual("key-id", config.kalshi_perpetual_api_key.get_secret_value())
        self.assertEqual("private-key", config.kalshi_perpetual_private_key.get_secret_value())

    def test_connector_is_registered_in_client_settings(self):
        all_settings = AllConnectorSettings.get_connector_settings()
        settings = all_settings["kalshi_perpetual"]

        self.assertEqual(ConnectorType.Derivative, settings.type)
        self.assertEqual("BTC-USD", settings.example_pair)
        self.assertTrue(settings.centralised)
        self.assertIs(utils.DEFAULT_FEES, settings.trade_fee_schema)
        self.assertIs(utils.KEYS, settings.config_keys)
        self.assertFalse(settings.is_sub_domain)
        self.assertEqual([], [name for name in all_settings if name.startswith("kalshi_perpetual_")])
        # The main class must live at this path with this name for the client to load it.
        self.assertEqual(
            "hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_derivative", settings.module_path()
        )
        self.assertEqual("KalshiPerpetualDerivative", settings.class_name())
