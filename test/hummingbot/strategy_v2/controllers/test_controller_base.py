import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase


class TestControllerBase(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        # Mocking the ControllerConfigBase
        self.mock_controller_config = ControllerConfigBase(
            id="test",
            controller_name="test_controller",
            candles_config=[
                CandlesConfig(
                    connector="binance_perpetual",
                    trading_pair="ETH-USDT",
                    interval="1m",
                    max_records=500
                )
            ]
        )

        # Mocking dependencies
        self.mock_market_data_provider = MagicMock(spec=MarketDataProvider)
        self.mock_actions_queue = AsyncMock(spec=asyncio.Queue)

        # Instantiating the ControllerBase
        self.controller = ControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )

    def test_initialize_candles(self):
        # Test whether candles are initialized correctly
        self.controller.initialize_candles()
        self.mock_market_data_provider.initialize_candles_feed.assert_called()

    def test_update_config(self):
        # Test the update_config method
        new_config = ControllerConfigBase(
            id="test_new",
            controller_name="new_test_controller",
            candles_config=[
                CandlesConfig(
                    connector="binance_perpetual",
                    trading_pair="ETH-USDT",
                    interval="3m",
                    max_records=500
                )
            ]
        )
        self.controller.update_config(new_config)
        # Controller name is not updatable
        self.assertEqual(self.controller.config.controller_name, "test_controller")

        # Candles config is updatable
        self.assertEqual(self.controller.config.candles_config[0].interval, "3m")

    async def test_control_task_market_data_privder_not_ready(self):
        type(self.controller.market_data_provider).ready = PropertyMock(return_value=False)
        self.controller.executors_update_event.set()
        await self.controller.control_task()
        # Check that no action is put in the queue
        self.mock_actions_queue.put.assert_not_called()

    async def test_control_task_executors_update_event_not_set(self):
        type(self.controller.market_data_provider).ready = PropertyMock(return_value=False)
        self.controller.executors_update_event.clear()
        await self.controller.control_task()
        # Check that no action is put in the queue
        self.mock_actions_queue.put.assert_not_called()

    async def test_control_task(self):
        type(self.controller.market_data_provider).ready = PropertyMock(return_value=True)
        self.controller.executors_update_event.set()
        self.controller.update_processed_data = AsyncMock()
        self.controller.determine_executor_actions = MagicMock(return_value=[])
        await self.controller.control_task()
        # Check that no action is put in the queue
        self.mock_actions_queue.put.assert_not_called()

    def test_to_format_status(self):
        # Test the to_format_status method
        status = self.controller.to_format_status()
        self.assertIsInstance(status, list)

    def test_controller_parse_candles_config_str_with_valid_input(self):
        # Test the parse_candles_config_str method

        input_str = "binance.BTC-USDT.1m.500:kraken.ETH-USD.5m.1000"
        expected_output = [
            CandlesConfig(connector="binance", trading_pair="BTC-USDT", interval="1m", max_records=500),
            CandlesConfig(connector="kraken", trading_pair="ETH-USD", interval="5m", max_records=1000)
        ]
        self.assertEqual(ControllerConfigBase.parse_candles_config_str(input_str), expected_output)

    def test_controller_parse_candles_config_str_with_empty_input(self):
        input_str = ""
        self.assertEqual(ControllerConfigBase.parse_candles_config_str(input_str), [])

    def test_controller_parse_candles_config_str_with_invalid_input(self):
        input_str = "binance.BTC-USDT.1m.notanumber"
        with self.assertRaises(ValueError) as e:
            ControllerConfigBase.parse_candles_config_str(input_str)
        self.assertEqual(str(e.exception), "Invalid max_records value 'notanumber' in segment 'binance.BTC-USDT.1m.notanumber'. max_records should be an integer.")
