import unittest

from pydantic import SecretStr

from hummingbot.client.settings import ConnectorSetting, ConnectorType
from hummingbot.connector.exchange.binance.binance_utils import BinanceConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema


class SettingsTest(unittest.TestCase):
    def test_non_trading_connector_instance_with_default_configuration_secrets_revealed(
        self
    ):
        api_key = "someKey"
        api_secret = "someSecret"
        config_map = BinanceConfigMap(
            binance_api_key=api_key,
            binance_api_secret=api_secret,
        )
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
