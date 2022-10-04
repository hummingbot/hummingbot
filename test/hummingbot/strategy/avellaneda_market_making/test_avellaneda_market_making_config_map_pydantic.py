import asyncio
import unittest
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Awaitable, Dict
from unittest.mock import patch

import yaml
from pydantic import validate_model

from hummingbot.client.config.config_helpers import ClientConfigAdapter, ConfigValidationError
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.strategy.avellaneda_market_making.avellaneda_market_making_config_map_pydantic import (
    AvellanedaMarketMakingConfigMap,
    DailyBetweenTimesModel,
    FromDateToDateModel,
    IgnoreHangingOrdersModel,
    InfiniteModel,
    MultiOrderLevelModel,
    SingleOrderLevelModel,
    TrackHangingOrdersModel,
)


class AvellanedaMarketMakingConfigMapPydanticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.exchange = "binance"
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        config_settings = self.get_default_map()
        self.config_map = ClientConfigAdapter(AvellanedaMarketMakingConfigMap(**config_settings))

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_default_map(self) -> Dict[str, str]:
        config_settings = {
            "exchange": self.exchange,
            "market": self.trading_pair,
            "execution_timeframe_mode": {
                "start_time": "09:30:00",
                "end_time": "16:00:00",
            },
            "order_amount": "10",
            "order_optimization_enabled": "yes",
            "risk_factor": "0.5",
            "order_refresh_time": "60",
            "inventory_target_base_pct": "50",
        }
        return config_settings

    def test_initial_sequential_build(self):
        config_map = ClientConfigAdapter(AvellanedaMarketMakingConfigMap.construct())
        config_settings = self.get_default_map()

        def build_config_map(cm: ClientConfigAdapter, cs: Dict):
            """This routine can be used in the create command, with slight modifications."""
            for key in cm.keys():
                client_data = cm.get_client_data(key)
                if client_data is not None and client_data.prompt_on_new:
                    self.assertIsInstance(client_data.prompt(cm), str)
                    if key == "execution_timeframe_model":
                        setattr(cm, key, "daily_between_times")  # simulate user input
                    else:
                        setattr(cm, key, cs[key])
                    new_value = getattr(cm, key)
                    if isinstance(new_value, ClientConfigAdapter):
                        build_config_map(new_value, cs[key])

        build_config_map(config_map, config_settings)
        hb_config = config_map.hb_config
        validate_model(hb_config.__class__, hb_config.__dict__)
        self.assertEqual(0, len(config_map.validate_model()))

    def test_order_amount_prompt(self):
        prompt = self.async_run_with_timeout(self.config_map.get_client_prompt("order_amount"))
        expected = f"What is the amount of {self.base_asset} per order?"

        self.assertEqual(expected, prompt)

    def test_maker_trading_pair_prompt(self):
        exchange = self.config_map.exchange
        example = AllConnectorSettings.get_example_pairs().get(exchange)

        prompt = self.async_run_with_timeout(self.config_map.get_client_prompt("market"))
        expected = f"Enter the token trading pair you would like to trade on {exchange} (e.g. {example})"

        self.assertEqual(expected, prompt)

    def test_execution_time_prompts(self):
        self.config_map.execution_timeframe_mode = FromDateToDateModel.Config.title
        model = self.config_map.execution_timeframe_mode
        prompt = self.async_run_with_timeout(model.get_client_prompt("start_datetime"))
        expected = "Please enter the start date and time (YYYY-MM-DD HH:MM:SS)"
        self.assertEqual(expected, prompt)
        prompt = self.async_run_with_timeout(model.get_client_prompt("end_datetime"))
        expected = "Please enter the end date and time (YYYY-MM-DD HH:MM:SS)"
        self.assertEqual(expected, prompt)

        self.config_map.execution_timeframe_mode = DailyBetweenTimesModel.Config.title
        model = self.config_map.execution_timeframe_mode
        prompt = self.async_run_with_timeout(model.get_client_prompt("start_time"))
        expected = "Please enter the start time (HH:MM:SS)"
        self.assertEqual(expected, prompt)
        prompt = self.async_run_with_timeout(model.get_client_prompt("end_time"))
        expected = "Please enter the end time (HH:MM:SS)"
        self.assertEqual(expected, prompt)

    @patch("hummingbot.client.config.strategy_config_data_types.validate_market_trading_pair")
    def test_validators(self, _):
        self.config_map.execution_timeframe_mode = "infinite"
        self.assertIsInstance(self.config_map.execution_timeframe_mode.hb_config, InfiniteModel)

        self.config_map.execution_timeframe_mode = "from_date_to_date"
        self.assertIsInstance(self.config_map.execution_timeframe_mode.hb_config, FromDateToDateModel)

        self.config_map.execution_timeframe_mode = "daily_between_times"
        self.assertIsInstance(self.config_map.execution_timeframe_mode.hb_config, DailyBetweenTimesModel)

        with self.assertRaises(ConfigValidationError) as e:
            self.config_map.execution_timeframe_mode = "XXX"

        error_msg = (
            "Invalid timeframe, please choose value from ['infinite', 'from_date_to_date', 'daily_between_times']"
        )
        self.assertEqual(error_msg, str(e.exception))

        self.config_map.execution_timeframe_mode = "from_date_to_date"
        model = self.config_map.execution_timeframe_mode
        model.start_datetime = "2021-01-01 12:00:00"
        model.end_datetime = "2021-01-01 15:00:00"

        self.assertEqual(datetime(2021, 1, 1, 12, 0, 0), model.start_datetime)
        self.assertEqual(datetime(2021, 1, 1, 15, 0, 0), model.end_datetime)

        with self.assertRaises(ConfigValidationError) as e:
            model.start_datetime = "2021-01-01 30:00:00"

        error_msg = "Incorrect date time format (expected is YYYY-MM-DD HH:MM:SS)"
        self.assertEqual(error_msg, str(e.exception))

        with self.assertRaises(ConfigValidationError) as e:
            model.start_datetime = "12:00:00"

        error_msg = "Incorrect date time format (expected is YYYY-MM-DD HH:MM:SS)"
        self.assertEqual(error_msg, str(e.exception))

        self.config_map.execution_timeframe_mode = "daily_between_times"
        model = self.config_map.execution_timeframe_mode
        model.start_time = "12:00:00"

        self.assertEqual(time(12, 0, 0), model.start_time)

        with self.assertRaises(ConfigValidationError) as e:
            model.start_time = "30:00:00"

        error_msg = "Incorrect time format (expected is HH:MM:SS)"
        self.assertEqual(error_msg, str(e.exception))

        with self.assertRaises(ConfigValidationError) as e:
            model.start_time = "2021-01-01 12:00:00"

        error_msg = "Incorrect time format (expected is HH:MM:SS)"
        self.assertEqual(error_msg, str(e.exception))

        self.config_map.order_levels_mode = "multi_order_level"
        model = self.config_map.order_levels_mode

        with self.assertRaises(ConfigValidationError) as e:
            model.order_levels = 1

        error_msg = "Value cannot be less than 2."
        self.assertEqual(error_msg, str(e.exception))

        model.order_levels = 3
        self.assertEqual(3, model.order_levels)

        self.config_map.hanging_orders_mode = "track_hanging_orders"
        model = self.config_map.hanging_orders_mode

        with self.assertRaises(ConfigValidationError) as e:
            model.hanging_orders_cancel_pct = "-1"

        error_msg = "Value must be between 0 and 100 (exclusive)."
        self.assertEqual(error_msg, str(e.exception))

        model.hanging_orders_cancel_pct = "3"
        self.assertEqual(3, model.hanging_orders_cancel_pct)

    def test_load_configs_from_yaml(self):
        cur_dir = Path(__file__).parent
        f_path = cur_dir / "test_config.yml"

        with open(f_path, "r") as file:
            data = yaml.safe_load(file)

        loaded_config_map = ClientConfigAdapter(AvellanedaMarketMakingConfigMap(**data))

        self.assertEqual(self.config_map, loaded_config_map)

    def test_configuring_execution_timeframe_mode(self):
        self.config_map.execution_timeframe_mode = InfiniteModel()

        self.config_map.execution_timeframe_mode = {
            "start_datetime": "2022-01-01 10:00:00",
            "end_datetime": "2022-01-02 10:00:00",
        }
        self.config_map.validate_model()

        self.assertIsInstance(self.config_map.execution_timeframe_mode.hb_config, FromDateToDateModel)
        self.assertEqual(self.config_map.execution_timeframe_mode.start_datetime, datetime(2022, 1, 1, 10))
        self.assertEqual(self.config_map.execution_timeframe_mode.end_datetime, datetime(2022, 1, 2, 10))

        self.config_map.execution_timeframe_mode = {
            "start_time": "10:00:00",
            "end_time": "11:00:00",
        }
        self.config_map.validate_model()

        self.assertIsInstance(self.config_map.execution_timeframe_mode.hb_config, DailyBetweenTimesModel)
        self.assertEqual(self.config_map.execution_timeframe_mode.start_time, time(10))
        self.assertEqual(self.config_map.execution_timeframe_mode.end_time, time(11))

        self.config_map.execution_timeframe_mode = {}
        self.config_map.validate_model()

        self.assertIsInstance(self.config_map.execution_timeframe_mode.hb_config, InfiniteModel)

    def test_configuring_order_levels_mode(self):
        self.config_map.order_levels_mode = SingleOrderLevelModel()

        self.config_map.order_levels_mode = {
            "order_levels": 2,
            "level_distances": 1,
        }
        self.config_map.validate_model()

        self.assertIsInstance(self.config_map.order_levels_mode.hb_config, MultiOrderLevelModel)
        self.assertEqual(self.config_map.order_levels_mode.order_levels, 2)
        self.assertEqual(self.config_map.order_levels_mode.level_distances, 1)

        self.config_map.order_levels_mode = {}
        self.config_map.validate_model()

        self.assertIsInstance(self.config_map.order_levels_mode.hb_config, SingleOrderLevelModel)

    def test_configuring_hanging_orders_mode(self):
        self.config_map.hanging_orders_mode = IgnoreHangingOrdersModel()

        self.config_map.hanging_orders_mode = {"hanging_orders_cancel_pct": 1}
        self.config_map.validate_model()

        self.assertIsInstance(self.config_map.hanging_orders_mode.hb_config, TrackHangingOrdersModel)
        self.assertEqual(self.config_map.hanging_orders_mode.hanging_orders_cancel_pct, Decimal("1"))

        self.config_map.hanging_orders_mode = {}
        self.config_map.validate_model()

        self.assertIsInstance(self.config_map.hanging_orders_mode.hb_config, IgnoreHangingOrdersModel)
