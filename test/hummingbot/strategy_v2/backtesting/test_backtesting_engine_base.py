"""Tests for BacktestingEngineBase.initialize_backtesting_data_provider (Issue #7886)."""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase


class TestBacktestingEngineCandlesConnector(unittest.TestCase):
    """Test that initialize_backtesting_data_provider uses candles_connector when available."""

    def _run_async(self, coro):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)

    def _make_engine_with_mocked_controller(self, connector_name, candles_connector=None, candles_config_list=None):
        """Create a BacktestingEngineBase with a mocked controller."""
        engine = BacktestingEngineBase()
        engine.backtesting_resolution = '1m'

        # Mock the controller and its config
        mock_config = MagicMock()
        mock_config.connector_name = connector_name
        mock_config.trading_pair = 'BTC-USDT'
        mock_config.candles_config = candles_config_list or []

        if candles_connector is not None:
            mock_config.candles_connector = candles_connector
        else:
            # Simulate the attribute not existing (like ControllerConfigBase)
            del mock_config.candles_connector

        mock_controller = MagicMock()
        mock_controller.config = mock_config
        mock_controller.market_data_provider = MagicMock()
        mock_controller.market_data_provider.initialize_candles_feed = AsyncMock()

        engine.controller = mock_controller
        return engine

    def test_uses_candles_connector_when_available(self):
        """When candles_connector is set and differs from connector_name, it should be used."""
        engine = self._make_engine_with_mocked_controller(
            connector_name='binance_perpetual',
            candles_connector='binance'
        )

        self._run_async(engine.initialize_backtesting_data_provider())

        # The first call should use candles_connector='binance', not 'binance_perpetual'
        calls = engine.controller.market_data_provider.initialize_candles_feed.call_args_list
        first_config = calls[0][0][0]  # first positional arg of first call
        self.assertIsInstance(first_config, CandlesConfig)
        self.assertEqual(first_config.connector, 'binance')
        self.assertEqual(first_config.trading_pair, 'BTC-USDT')
        self.assertEqual(first_config.interval, '1m')

    def test_falls_back_to_connector_name_when_no_candles_connector(self):
        """When candles_connector is not set, it should fall back to connector_name."""
        engine = self._make_engine_with_mocked_controller(
            connector_name='binance_perpetual',
            candles_connector=None  # attribute deleted in helper
        )

        self._run_async(engine.initialize_backtesting_data_provider())

        calls = engine.controller.market_data_provider.initialize_candles_feed.call_args_list
        first_config = calls[0][0][0]
        self.assertIsInstance(first_config, CandlesConfig)
        self.assertEqual(first_config.connector, 'binance_perpetual')

    def test_uses_connector_name_when_candles_connector_is_empty_string(self):
        """When candles_connector is an empty string, it should fall back to connector_name."""
        engine = self._make_engine_with_mocked_controller(
            connector_name='binance_perpetual',
            candles_connector=''
        )

        self._run_async(engine.initialize_backtesting_data_provider())

        calls = engine.controller.market_data_provider.initialize_candles_feed.call_args_list
        first_config = calls[0][0][0]
        self.assertEqual(first_config.connector, 'binance_perpetual')

    def test_also_initializes_additional_candles_configs(self):
        """Should still initialize additional candles_config entries from the controller."""
        extra_config = CandlesConfig(connector='kucoin', trading_pair='ETH-USDT', interval='5m')
        engine = self._make_engine_with_mocked_controller(
            connector_name='binance_perpetual',
            candles_connector='binance',
            candles_config_list=[extra_config]
        )

        self._run_async(engine.initialize_backtesting_data_provider())

        calls = engine.controller.market_data_provider.initialize_candles_feed.call_args_list
        # Should have 2 calls: base backtesting config + the extra one
        self.assertEqual(len(calls), 2)
        second_config = calls[1][0][0]
        self.assertEqual(second_config.connector, 'kucoin')
        self.assertEqual(second_config.trading_pair, 'ETH-USDT')


if __name__ == '__main__':
    unittest.main()
