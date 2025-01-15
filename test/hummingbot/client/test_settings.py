import unittest
from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from hummingbot.client.settings import ConnectorSetting, ConnectorType
from hummingbot.connector.exchange.binance.binance_utils import BinanceConfigMap
from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_api_data_source import (
    InjectiveAPIDataSource,
)
from hummingbot.connector.gateway.clob_spot.data_sources.kujira.kujira_api_data_source import KujiraAPIDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeSchema


class SettingsTest(unittest.TestCase):
    def test_non_trading_connector_instance_with_default_configuration_secrets_revealed(self):
        api_key = "someKey"
        api_secret = "someSecret"
        config_map = BinanceConfigMap(binance_api_key=api_key, binance_api_secret=api_secret)
        conn_settings = ConnectorSetting(
            name="binance",
            type=ConnectorType.Exchange,
            example_pair="BTC-USDT",
            centralised=True,
            use_ethereum_wallet=False,
            trade_fee_schema=TradeFeeSchema(),
            config_keys=config_map,
            is_sub_domain=False,
            parent_name=None,
            domain_parameter=None,
            use_eth_gas_lookup=False,
        )
        connector = conn_settings.non_trading_connector_instance_with_default_configuration()

        self.assertNotIsInstance(connector.api_key, SecretStr)
        self.assertEqual(api_key, connector.api_key)
        self.assertNotIsInstance(connector.secret_key, SecretStr)
        self.assertEqual(api_secret, connector.secret_key)

    def test_conn_init_parameters_for_cex_connector(self):
        api_key = "someKey"
        api_secret = "someSecret"
        config_map = BinanceConfigMap(binance_api_key=api_key, binance_api_secret=api_secret)
        conn_settings = ConnectorSetting(
            name="binance",
            type=ConnectorType.Exchange,
            example_pair="BTC-USDT",
            centralised=True,
            use_ethereum_wallet=False,
            trade_fee_schema=TradeFeeSchema(),
            config_keys=config_map,
            is_sub_domain=False,
            parent_name=None,
            domain_parameter=None,
            use_eth_gas_lookup=False,
        )

        api_keys = {"binance_api_key": api_key, "binance_api_secret": api_secret}
        params = conn_settings.conn_init_parameters(api_keys=api_keys)
        expected_params = {
            "binance_api_key": api_key,
            "binance_api_secret": api_secret,
            "trading_pairs": [],
            "trading_required": False,
            "client_config_map": None,
        }

        self.assertEqual(expected_params, params)

    @patch("hummingbot.client.settings.GatewayConnectionSetting.get_connector_spec_from_market_name")
    def test_conn_init_parameters_for_gateway_generic_connector(
        self, get_connector_spec_from_market_name_mock: MagicMock
    ):
        get_connector_spec_from_market_name_mock.return_value = {
            "connector": "vvs",
            "chain": "cronos",
            "network": "mainnet",
            "trading_type": "AMM",
            "wallet_address": "0xA86b66F4e7DC45a943D71a11c7DDddE341246682",  # noqa: mock
        }
        conn_settings = ConnectorSetting(
            name="vvs_cronos_mainnet",
            type=ConnectorType.AMM,
            example_pair="WETH-USDC",
            centralised=True,
            use_ethereum_wallet=False,
            trade_fee_schema=TradeFeeSchema(),
            config_keys=None,
            is_sub_domain=False,
            parent_name=None,
            domain_parameter=None,
            use_eth_gas_lookup=False,
        )

        expected_params = {
            "connector_name": "vvs",
            "chain": "cronos",
            "network": "mainnet",
            "address": "0xA86b66F4e7DC45a943D71a11c7DDddE341246682",  # noqa: mock
            "trading_pairs": [],
            "trading_required": False,
            "client_config_map": None,
        }
        params = conn_settings.conn_init_parameters()

        self.assertEqual(expected_params, params)

    @patch("hummingbot.client.settings.GatewayConnectionSetting.get_connector_spec_from_market_name")
    def test_conn_init_parameters_for_gateway_injective_connector(
        self, get_connector_spec_from_market_name_mock: MagicMock
    ):
        get_connector_spec_from_market_name_mock.return_value = {
            "connector": "injective",
            "chain": "injective",
            "network": "mainnet",
            "trading_type": "CLOB_SPOT",
            "wallet_address": "0xA86b66F4e7DC45a943D71a11c7DDddE341246682",  # noqa: mock
        }
        conn_settings = ConnectorSetting(
            name="injective_injective_mainnet",
            type=ConnectorType.CLOB_SPOT,
            example_pair="WETH-USDC",
            centralised=True,
            use_ethereum_wallet=False,
            trade_fee_schema=TradeFeeSchema(),
            config_keys=None,
            is_sub_domain=False,
            parent_name=None,
            domain_parameter=None,
            use_eth_gas_lookup=False,
        )

        expected_params_without_api_data_source = {
            "connector_name": "injective",
            "chain": "injective",
            "network": "mainnet",
            "address": "0xA86b66F4e7DC45a943D71a11c7DDddE341246682",  # noqa: mock
            "trading_pairs": [],
            "trading_required": False,
            "client_config_map": None,
        }
        params = conn_settings.conn_init_parameters()

        self.assertIn("api_data_source", params)

        api_data_source = params.pop("api_data_source")

        self.assertIsInstance(api_data_source, InjectiveAPIDataSource)
        self.assertEqual(expected_params_without_api_data_source, params)

    @patch("hummingbot.client.settings.GatewayConnectionSetting.get_connector_spec_from_market_name")
    def test_conn_init_parameters_for_gateway_kujira_connector(
        self, get_connector_spec_from_market_name_mock: MagicMock
    ):
        get_connector_spec_from_market_name_mock.return_value = {
            "connector": "kujira",
            "chain": "kujira",
            "network": "mainnet",
            "trading_type": "CLOB_SPOT",
            "wallet_address": "0xA86b66F4e7DC45a943D71a11c7DDddE341246682",  # noqa: mock
        }
        conn_settings = ConnectorSetting(
            name="kujira_kujira_mainnet",
            type=ConnectorType.CLOB_SPOT,
            example_pair="KUJI-DEMO",
            centralised=True,
            use_ethereum_wallet=False,
            trade_fee_schema=TradeFeeSchema(),
            config_keys=None,
            is_sub_domain=False,
            parent_name=None,
            domain_parameter=None,
            use_eth_gas_lookup=False,
        )

        expected_params_without_api_data_source = {
            "connector_name": "kujira",
            "chain": "kujira",
            "network": "mainnet",
            "address": "0xA86b66F4e7DC45a943D71a11c7DDddE341246682",  # noqa: mock
            "trading_pairs": [],
            "trading_required": False,
            "client_config_map": None,
        }
        params = conn_settings.conn_init_parameters()

        self.assertIn("api_data_source", params)

        api_data_source = params.pop("api_data_source")

        self.assertIsInstance(api_data_source, KujiraAPIDataSource)
        self.assertEqual(expected_params_without_api_data_source, params)
