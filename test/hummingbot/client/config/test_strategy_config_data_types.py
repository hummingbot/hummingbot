import asyncio
import json
from typing import Awaitable, Dict
from unittest import TestCase
from unittest.mock import patch

from hummingbot.client import settings
from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.client.config.config_helpers import ClientConfigAdapter, ConfigValidationError
from hummingbot.client.config.strategy_config_data_types import (
    BaseTradingStrategyConfigMap,
    BaseTradingStrategyMakerTakerConfigMap,
)
from hummingbot.client.settings import AllConnectorSettings, ConnectorType


class BaseStrategyConfigMapTest(TestCase):
    def test_generate_yml_output_dict_title(self):
        class DummyStrategy(BaseClientModel):
            class Config:
                title = "pure_market_making"

            strategy: str = "pure_market_making"

        instance = ClientConfigAdapter(DummyStrategy())
        res_str = instance.generate_yml_output_str_with_comments()

        expected_str = """\
#####################################
###   pure_market_making config   ###
#####################################

strategy: pure_market_making
"""

        self.assertEqual(expected_str, res_str)


class BaseTradingStrategyConfigMapTest(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.exchange = "binance"
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        # Reset the list of connectors (there could be changes introduced by other tests when running the suite
        AllConnectorSettings.create_connector_settings()

    def setUp(self) -> None:
        super().setUp()
        config_settings = self.get_default_map()
        self.config_map = ClientConfigAdapter(BaseTradingStrategyConfigMap(**config_settings))

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_default_map(self) -> Dict[str, str]:
        config_settings = {
            "strategy": "pure_market_making",
            "exchange": self.exchange,
            "market": self.trading_pair,
        }
        return config_settings

    @patch("hummingbot.client.config.strategy_config_data_types.validate_market_trading_pair")
    def test_validators(self, validate_market_trading_pair_mock):
        with self.assertRaises(ConfigValidationError) as e:
            self.config_map.exchange = "test-exchange"

        error_msg = "Invalid exchange, please choose value from "
        self.assertTrue(str(e.exception).startswith(error_msg))

        alt_pair = "ETH-USDT"
        error_msg = "Failed"
        validate_market_trading_pair_mock.side_effect = (
            lambda m, v: None if v in [self.trading_pair, alt_pair] else error_msg
        )

        self.config_map.market = alt_pair
        self.assertEqual(alt_pair, self.config_map.market)

        with self.assertRaises(ConfigValidationError) as e:
            self.config_map.market = "XXX-USDT"

        self.assertTrue(str(e.exception).startswith(error_msg))

    def test_jason_schema_includes_all_connectors_for_exchange_field(self):

        schema = BaseTradingStrategyConfigMap.schema_json()
        schema_dict = json.loads(schema)

        self.assertIn("Exchanges", schema_dict["definitions"])
        expected_connectors = [connector_setting.name for connector_setting in
                               AllConnectorSettings.get_connector_settings().values()
                               if connector_setting.type is ConnectorType.Exchange]
        expected_connectors.extend(settings.PAPER_TRADE_EXCHANGES)
        expected_connectors.sort()
        self.assertEqual(expected_connectors, schema_dict["definitions"]["Exchanges"]["enum"])


class BaseTradingStrategyMakerTakerConfigMapTests(TestCase):

    def test_maker_field_jason_schema_includes_all_connectors_for_exchange_field(self):

        schema = BaseTradingStrategyMakerTakerConfigMap.schema_json()
        schema_dict = json.loads(schema)

        self.assertIn("MakerMarkets", schema_dict["definitions"])
        expected_connectors = [connector_setting.name for connector_setting in
                               AllConnectorSettings.get_connector_settings().values()
                               if connector_setting.type is ConnectorType.Exchange]
        expected_connectors.extend(settings.PAPER_TRADE_EXCHANGES)
        expected_connectors.sort()
        self.assertEqual(expected_connectors, schema_dict["definitions"]["MakerMarkets"]["enum"])

    def test_taker_field_jason_schema_includes_all_connectors_for_exchange_field(self):

        schema = BaseTradingStrategyMakerTakerConfigMap.schema_json()
        schema_dict = json.loads(schema)

        self.assertIn("TakerMarkets", schema_dict["definitions"])
        expected_connectors = [connector_setting.name for connector_setting in
                               AllConnectorSettings.get_connector_settings().values()
                               if connector_setting.type is ConnectorType.Exchange]
        expected_connectors.extend(settings.PAPER_TRADE_EXCHANGES)
        expected_connectors.sort()
        self.assertEqual(expected_connectors, schema_dict["definitions"]["TakerMarkets"]["enum"])
