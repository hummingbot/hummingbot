import mock
import unittest
from copy import deepcopy
from unittest.mock import MagicMock

import hummingbot.strategy.perpetual_market_making.perpetual_market_making_config_map as config_map_module
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
from hummingbot.strategy.perpetual_market_making.perpetual_market_making_config_map import (
    maker_trading_pair_prompt,
    on_validate_price_source,
    order_amount_prompt,
    perpetual_market_making_config_map as perpetual_mm_config_map,
    validate_price_type,
)


class TestPMMConfigMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.derivative = "binance_perpetual"
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(perpetual_mm_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            perpetual_mm_config_map[key] = value

    def test_on_validate_price_source_non_external_market_reset(self):
        perpetual_mm_config_map["price_source_derivative"].value = "an_extmkt"
        perpetual_mm_config_map["price_source_market"].value = self.trading_pair

        on_validate_price_source(value="current_market")

        self.assertIsNone(perpetual_mm_config_map["price_source_derivative"].value)
        self.assertIsNone(perpetual_mm_config_map["price_source_market"].value)

    def test_on_validate_price_source_non_custom_api_reset(self):
        perpetual_mm_config_map["price_source_custom_api"].value = "https://someurl.com"

        on_validate_price_source(value="current_market")

        self.assertIsNone(perpetual_mm_config_map["price_source_custom_api"].value)

    def test_on_validate_price_source_custom_api_set_price_type(self):
        on_validate_price_source(value="custom_api")

        self.assertEqual(perpetual_mm_config_map["price_type"].value, "custom")

    def test_validate_price_type_non_custom_api(self):
        perpetual_mm_config_map["price_source"].value = "current_market"

        error = validate_price_type(value="mid_price")
        self.assertIsNone(error)
        error = validate_price_type(value="last_price")
        self.assertIsNone(error)
        error = validate_price_type(value="last_own_trade_price")
        self.assertIsNone(error)
        error = validate_price_type(value="best_bid")
        self.assertIsNone(error)
        error = validate_price_type(value="best_ask")
        self.assertIsNone(error)

        error = validate_price_type(value="custom")
        self.assertIsNotNone(error)

    def test_validate_price_type_custom_api(self):
        perpetual_mm_config_map["price_source"].value = "custom_api"

        error = validate_price_type(value="mid_price")
        self.assertIsNotNone(error)
        error = validate_price_type(value="last_price")
        self.assertIsNotNone(error)
        error = validate_price_type(value="last_own_trade_price")
        self.assertIsNotNone(error)
        error = validate_price_type(value="best_bid")
        self.assertIsNotNone(error)
        error = validate_price_type(value="best_ask")
        self.assertIsNotNone(error)

        error = validate_price_type(value="custom")
        self.assertIsNone(error)

    def test_order_amount_prompt(self):
        perpetual_mm_config_map["market"].value = self.trading_pair
        prompt = order_amount_prompt()
        expected = f"What is the amount of {self.base_asset} per order? >>> "

        self.assertEqual(expected, prompt)

    def test_maker_trading_prompt(self):
        perpetual_mm_config_map["derivative"].value = self.derivative
        example = AllConnectorSettings.get_example_pairs().get(self.derivative)

        prompt = maker_trading_pair_prompt()
        expected = f"Enter the token trading pair you would like to trade on {self.derivative} (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)

    def test_validate_derivative_trading_pair(self):
        fetcher_mock = MagicMock()
        type(fetcher_mock).ready = mock.PropertyMock(return_value=True)
        type(fetcher_mock).trading_pairs = mock.PropertyMock(return_value={"test_market": ["BTC-USDT"]})
        TradingPairFetcher._sf_shared_instance = fetcher_mock

        perpetual_mm_config_map.get("derivative").value = "test_market"

        result = config_map_module.validate_derivative_trading_pair("BTC-USDT")
        self.assertIsNone(result)

        result = config_map_module.validate_derivative_trading_pair("NON-EXISTENT")
        self.assertEqual("NON-EXISTENT is not an active market on test_market.", result)

    def test_validate_derivative_position_mode(self):
        self.assertIsNone(config_map_module.validate_derivative_position_mode("One-way"))
        self.assertIsNone(config_map_module.validate_derivative_position_mode("Hedge"))

        self.assertEqual(
            "Position mode can either be One-way or Hedge mode",
            config_map_module.validate_derivative_position_mode("Invalid"))

    def test_validate_price_source(self):
        self.assertIsNone(config_map_module.validate_price_source("current_market"))
        self.assertIsNone(config_map_module.validate_price_source("external_market"))
        self.assertIsNone(config_map_module.validate_price_source("custom_api"))

        self.assertEqual(
            "Invalid price source type.",
            config_map_module.validate_price_source("invalid_market")
        )

    def test_price_source_market_prompt(self):
        perpetual_mm_config_map.get("price_source_derivative").value = "test_market"
        self.assertEqual(
            "Enter the token trading pair on test_market >>> ",
            config_map_module.price_source_market_prompt()
        )

    @mock.patch("hummingbot.client.settings.AllConnectorSettings.get_derivative_names")
    @mock.patch("hummingbot.client.settings.AllConnectorSettings.get_exchange_names")
    def test_price_source_derivative_validator(self, get_derivatives_mock, get_exchange_mock):
        get_derivatives_mock.return_value = ["derivative_connector"]
        get_exchange_mock.return_value = ["exchange_connector"]

        perpetual_mm_config_map.get("derivative").value = "test_market"
        self.assertEqual(
            "Price source derivative cannot be the same as maker derivative.",
            config_map_module.validate_price_source_derivative("test_market")
        )

        self.assertEqual(
            "Price source must must be a valid exchange or derivative connector.",
            config_map_module.validate_price_source_derivative("invalid")
        )

        self.assertIsNone(config_map_module.validate_price_source_derivative("derivative_connector"))

    def test_on_validate_price_source_derivative(self):
        perpetual_mm_config_map.get("price_source_market").value = "MARKET"
        config_map_module.on_validated_price_source_derivative("Something")
        self.assertEqual("MARKET", perpetual_mm_config_map.get("price_source_market").value)

        config_map_module.on_validated_price_source_derivative(None)
        self.assertIsNone(perpetual_mm_config_map.get("price_source_market").value)

    def test_validate_price_source_market(self):
        fetcher_mock = MagicMock()
        type(fetcher_mock).ready = mock.PropertyMock(return_value=True)
        type(fetcher_mock).trading_pairs = mock.PropertyMock(return_value={"test_market": ["BTC-USDT"]})
        TradingPairFetcher._sf_shared_instance = fetcher_mock

        perpetual_mm_config_map.get("price_source_derivative").value = "test_market"

        result = config_map_module.validate_price_source_market("BTC-USDT")
        self.assertIsNone(result)

        result = config_map_module.validate_price_source_market("NON-EXISTENT")
        self.assertEqual("NON-EXISTENT is not an active market on test_market.", result)

    def test_validate_price_floor_ceiling(self):
        result = config_map_module.validate_price_floor_ceiling("Not a number")
        self.assertEqual("Not a number is not in decimal format.", result)

        result = config_map_module.validate_price_floor_ceiling("-0.5")
        self.assertEqual("Value must be more than 0 or -1 to disable this feature.", result)
        result = config_map_module.validate_price_floor_ceiling("0")
        self.assertEqual("Value must be more than 0 or -1 to disable this feature.", result)

        result = config_map_module.validate_price_floor_ceiling("-1")
        self.assertIsNone(result)
        result = config_map_module.validate_price_floor_ceiling("0.1")
        self.assertIsNone(result)
