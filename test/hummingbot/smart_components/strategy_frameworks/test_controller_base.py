import unittest
from unittest.mock import MagicMock

import pandas as pd

from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.strategy_frameworks.controller_base import ControllerBase, ControllerConfigBase


class TestControllerBase(unittest.TestCase):

    def setUp(self):
        # Mocking the CandlesConfig
        self.mock_candles_config = CandlesConfig(
            connector="binance",
            trading_pair="BTC-USDT",
            interval="1m"
        )

        # Mocking the ControllerConfigBase
        self.mock_controller_config = ControllerConfigBase(
            id="test",
            strategy_name="dman_strategy",
            exchange="binance_perpetual",
            trading_pair="BTC-USDT",
            candles_config=[self.mock_candles_config],
        )

        # Instantiating the ControllerBase
        self.controller = ControllerBase(
            config=self.mock_controller_config,
        )

    def test_initialize_candles_live_mode(self):
        candles = self.controller.initialize_candles([self.mock_candles_config])
        self.assertTrue(len(candles) == 1)

    def test_initialize_candles_non_live_mode(self):
        self.controller.initialize_candles([self.mock_candles_config])
        self.assertTrue(len(self.controller.candles) == 1)

    def test_get_close_price(self):
        mock_candle = MagicMock()
        mock_candle.name = "binance_BTC-USDT"
        mock_candle._trading_pair = "BTC-USDT"
        mock_candle.interval = "1m"
        mock_candle.candles_df = pd.DataFrame({"close": [100.0, 200.0, 300.0],
                                               "open": [100.0, 200.0, 300.0]})
        self.controller.candles = [mock_candle]
        close_price = self.controller.get_close_price("BTC-USDT")
        self.assertEqual(close_price, 300)

    def test_get_candles_by_connector_trading_pair(self):
        mock_candle = MagicMock()
        mock_candle.name = "binance_BTC-USDT"
        mock_candle.interval = "1m"
        result = self.controller.get_candles_by_connector_trading_pair("binance", "BTC-USDT")
        self.assertEqual(list(result.keys()), ["1m"])

    def test_get_candle(self):
        mock_candle = MagicMock()
        mock_candle.name = "binance_BTC-USDT"
        mock_candle.interval = "1m"
        self.controller.candles = [mock_candle]
        result = self.controller.get_candle("binance", "BTC-USDT", "1m")
        self.assertEqual(result, mock_candle)

    def test_all_candles_ready(self):
        mock_candle = MagicMock()
        mock_candle.is_ready = True
        self.controller.candles = [mock_candle]
        self.assertTrue(self.controller.all_candles_ready)

    def test_start(self):
        mock_candle = MagicMock()
        self.controller.candles = [mock_candle]
        self.controller.start()
        mock_candle.start.assert_called_once()

    def test_stop(self):
        mock_candle = MagicMock()
        self.controller.candles = [mock_candle]
        self.controller.stop()
        mock_candle.stop.assert_called_once()

    def test_get_csv_prefix(self):
        prefix = self.controller.get_csv_prefix()
        self.assertEqual(prefix, "dman_strategy")

    def test_to_format_status(self):
        status = self.controller.to_format_status()
        self.assertEqual("     id: test", status[1])
