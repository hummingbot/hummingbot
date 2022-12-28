import unittest
from decimal import Decimal
from pathlib import Path
from typing import Dict
from unittest.mock import patch

import yaml

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import ConnectorSetting, ConnectorType
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.strategy.hedge.hedge_config_map_pydantic import HedgeConfigMap, MarketConfigMap


class HedgeConfigMapPydanticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hedge_connector = "bybit_perpetual_testnet"
        cls.connector = "binance"

    @patch("hummingbot.client.settings.AllConnectorSettings.get_exchange_names")
    @patch("hummingbot.client.settings.AllConnectorSettings.get_connector_settings")
    def setUp(self, get_connector_settings_mock, get_exchange_names_mock) -> None:
        super().setUp()
        config_settings = self.get_default_map()
        get_exchange_names_mock.return_value = set(self.get_mock_connector_settings().keys())
        get_connector_settings_mock.return_value = self.get_mock_connector_settings()
        self.config_map = ClientConfigAdapter(HedgeConfigMap(**config_settings))

    def get_mock_connector_settings(self):
        conf_var_connector_maker = ConfigVar(key='mock_paper_exchange', prompt="")
        conf_var_connector_maker.value = 'mock_paper_exchange'

        settings = {
            "mock_paper_exchange": ConnectorSetting(
                name='mock_paper_exchange',
                type=ConnectorType.Exchange,
                example_pair='BTC-ETH',
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
                    'connector': conf_var_connector_maker
                },
                is_sub_domain=False,
                parent_name=None,
                domain_parameter=None,
                use_eth_gas_lookup=False)
        }

        return settings

    def get_default_map(self) -> Dict[str, str]:
        config_settings = {
            "hedge_connector": self.hedge_connector,
            "hedge_markets": self.trading_pair,
            "connector_0": {
                "connector": self.connector,
                "markets": [self.trading_pair],
                "offsets": [0]},
            "connector_1": 'n',
            "connector_2": 'n',
            "connector_3": 'n',
            "connector_4": 'n',
        }
        return config_settings

    def test_hedge_markets_prompt(self):
        self.config_map.hedge_connector = self.connector
        self.config_map.hedge_markets = self.trading_pair
        self.config_map.value_mode = True
        self.assertEqual(
            self.config_map.hedge_markets_prompt(self.config_map),
            f"Enter the trading pair you would like to hedge on {self.connector}. (Example: BTC-USDT)",
        )
        self.config_map.value_mode = False
        self.assertEqual(
            self.config_map.hedge_markets_prompt(self.config_map),
            f"Enter the list of trading pair you would like to hedge on {self.connector}. comma seperated. \
            (Example: BTC-USDT,ETH-USDT) Only markets with the same base as the hedge markets will be hedged."
        )

    def test_hedge_offsets_prompt(self):
        self.config_map.hedge_connector = self.connector
        self.config_map.hedge_markets = self.trading_pair
        self.config_map.value_mode = True
        base = self.trading_pair.split("-")[0]
        self.assertEqual(
            self.config_map.hedge_offsets_prompt(self.config_map),
            f"Enter the offset for {base}. (Example: 0.1 = +0.1{base} used in calculation of hedged value)"
        )
        self.config_map.value_mode = False
        self.assertEqual(
            self.config_map.hedge_offsets_prompt(self.config_map),
            "Enter the offsets to use to hedge the markets comma seperated. "
            "(Example: 0.1,-0.2 = +0.1BTC,-0.2ETH, 0LTC will be offset for the exchange amount "
            "if markets is BTC-USDT,ETH-USDT,LTC-USDT)"
        )

    def test_trading_pair_prompt(self):
        connector_map = MarketConfigMap(
            connector=self.connector,
            markets = self.trading_pair,
            offsets = [Decimal("0")]
        )
        connector_map.trading_pair_prompt(connector_map)

    def test_load_configs_from_yaml(self):
        cur_dir = Path(__file__).parent
        f_path = cur_dir / "test_config.yml"

        with open(f_path, "r") as file:
            data = yaml.safe_load(file)

        loaded_config_map = ClientConfigAdapter(HedgeConfigMap(**data))
        self.assertIsInstance(loaded_config_map, ClientConfigAdapter)
