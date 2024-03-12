import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
from pandas._testing import assert_frame_equal

from hummingbot.smart_components.backtesting.backtesting_engine_base import BacktestingEngineBase


class TestBacktestingEngineBase(unittest.TestCase):

    @patch("hummingbot.smart_components.controllers.controller_base.ControllerBase")
    def setUp(self, MockControllerBase):
        self.controller = MockControllerBase()
        self.backtesting_engine = BacktestingEngineBase(self.controller)

    def test_filter_df_by_time(self):
        df = pd.DataFrame({
            "timestamp": pd.date_range(start="2021-01-01", end="2021-01-05", freq="D")
        })
        filtered_df = self.backtesting_engine.filter_df_by_time(df, "2021-01-02", "2021-01-04")
        self.assertEqual(len(filtered_df), 3)
        self.assertEqual(filtered_df["timestamp"].min(), pd.Timestamp("2021-01-02"))
        self.assertEqual(filtered_df["timestamp"].max(), pd.Timestamp("2021-01-04"))

    def test_summarize_results(self):
        initial_date = datetime(2023, 3, 16, 0, 0, tzinfo=timezone.utc)
        initial_timestamp = int(initial_date.timestamp())
        minute = 60
        timestamps = [
            initial_timestamp,
            initial_timestamp + minute * 2,
            initial_timestamp + minute * 4,
            initial_timestamp + minute * 6,
            initial_timestamp + minute * 8
        ]

        # Assuming each trade closes after 60 seconds (1 minute)
        close_timestamps = [timestamp + 60 for timestamp in timestamps]
        executors_df = pd.DataFrame({
            "timestamp": timestamps,
            "close_timestamp": close_timestamps,
            "exchange": ["binance_perpetual"] * 5,
            "trading_pair": ["HBOT-USDT"] * 5,
            "side": ["BUY", "BUY", "SELL", "SELL", "BUY"],
            "amount": [10, 20, 10, 20, 10],
            "trade_pnl": [0.2, 0.1, -0.1, -0.2, 0.2],
            "trade_pnl_quote": [0, 0, 0, 0, 0],
            "cum_fee_quote": [0, 0, 0, 0, 0],
            "net_pnl": [1, 2, -1, -2, 1],
            "net_pnl_quote": [0.1, 0.2, -0.1, -0.2, 0.1],
            "profitable": [1, 1, 0, 0, 1],
            "signal": [1, -1, 1, 1, 1],
            "executor_status": ["COMPLETED"] * 5,
            "close_type": ["EXPIRED", "EXPIRED", "EXPIRED", "EXPIRED", "EXPIRED"],
            "entry_price": [5, 5, 5, 5, 5],
            "close_price": [5, 5, 5, 5, 5],
            "sl": [0.03] * 5,
            "tp": [0.02] * 5,
            "tl": [86400] * 5,
            "leverage": [10] * 5,
            "inventory": [10, 10, 10, 10, 10],
        })
        executors_df.index = pd.to_datetime(executors_df["timestamp"], unit="s")
        executors_df["close_time"] = pd.to_datetime(executors_df["close_timestamp"], unit="s")
        result = self.backtesting_engine.summarize_results(executors_df)
        self.assertEqual(result["net_pnl"], 1)  # 1 + 2 - 1 - 2 + 1
        self.assertEqual(round(result["net_pnl_quote"], 2), 0.1)  # 0.1 + 0.2 - 0.1 - 0.2 + 0.1
        self.assertEqual(result["total_executors"], 5)
        self.assertEqual(result["total_executors_with_position"], 5)
        self.assertEqual(result["total_long"], 3)  # 3 BUYs
        self.assertEqual(result["total_short"], 2)  # 2 SELLs
        self.assertEqual(result["close_types"]["EXPIRED"], 5)  # All are "EXPIRED"
        self.assertEqual(result["accuracy"], 3 / 5)  # 3 out of 5 trades were profitable
        self.assertEqual(round(result["duration_minutes"], 3), 9)  # 4 minutes between the first and last trade
        self.assertEqual(round(result["avg_trading_time_minutes"], 3), 1)  # Average of 1 minute between trades

    def test_summarize_results_empty(self):
        result = self.backtesting_engine.summarize_results(pd.DataFrame())
        self.assertEqual(result["net_pnl"], 0)
        self.assertEqual(result["net_pnl_quote"], 0)

    def test_apply_triple_barrier_method(self):
        # Setup test data
        df = pd.DataFrame({
            "timestamp": pd.date_range(start="2021-01-01", periods=5, freq="H").astype(int) / 10 ** 9,
            "close": [100, 105, 110, 115, 120],
            "signal": [1, -1, 1, -1, 1]
        })
        df["timestamp"] = df["timestamp"].astype("int")

        result_df = self.backtesting_engine.apply_triple_barrier_method(df)

        # Assertions
        self.assertTrue("take_profit_price" in result_df.columns)
        self.assertTrue("stop_loss_price" in result_df.columns)
        self.assertTrue("close_time" in result_df.columns)
        self.assertTrue("close_type" in result_df.columns)
        self.assertTrue("stop_loss_time" in result_df.columns)
        self.assertTrue("take_profit_time" in result_df.columns)

    @patch("hummingbot.smart_components.backtesting.backtesting_engine_base.BacktestingEngineBase.simulate_execution")
    @patch("hummingbot.smart_components.backtesting.backtesting_engine_base.BacktestingEngineBase.get_data")
    def test_run_backtesting(self, mock_get_data, mock_simulate_execution):
        # Setup test data
        processed_data = pd.DataFrame()
        executors_df = pd.DataFrame()
        results = {"net_pnl": 100}

        # Setup mock methods
        mock_get_data.return_value = processed_data
        mock_simulate_execution.return_value = executors_df

        self.backtesting_engine.summarize_results = MagicMock(return_value=results)

        output = self.backtesting_engine.run_backtesting()

        # Assertions
        mock_get_data.assert_called_once()
        mock_simulate_execution.assert_called_once()

        # Use assert_frame_equal for DataFrame comparison
        assert_frame_equal(output["processed_data"], processed_data)
        assert_frame_equal(output["executors_df"], executors_df)
        self.assertEqual(output["results"], results)
