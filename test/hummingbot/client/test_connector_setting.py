from decimal import Decimal
from unittest import TestCase

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import ConnectorSetting, ConnectorType
from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
from hummingbot.core.data_type.trade_fee import TradeFeeSchema


class ConnectorSettingTests(TestCase):

    def test_connector_setting_creates_non_trading_connector_instance(self):
        setting = ConnectorSetting(
            name='binance',
            type=ConnectorType.Exchange,
            example_pair='ZRX-ETH',
            centralised=True,
            use_ethereum_wallet=False,
            trade_fee_schema=TradeFeeSchema(
                percent_fee_token=None,
                maker_percent_fee_decimal=Decimal('0.001'),
                taker_percent_fee_decimal=Decimal('0.001'),
                buy_percent_fee_deducted_from_returns=False,
                maker_fixed_fees=[],
                taker_fixed_fees=[]),
            config_keys={
                'binance_api_key': ConfigVar(key='binance_api_key', prompt=""),
                'binance_api_secret': ConfigVar(key='binance_api_secret', prompt="")},
            is_sub_domain=False,
            parent_name=None,
            domain_parameter=None,
            use_eth_gas_lookup=False)

        connector: BinanceExchange = setting.non_trading_connector_instance_with_default_configuration()

        self.assertEqual("binance", connector.name)
        self.assertEqual("com", connector._domain)
        self.assertEqual("", connector._auth.api_key)
        self.assertEqual("", connector._auth.secret_key)
        self.assertFalse(connector._trading_required)
