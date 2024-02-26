import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.smart_components.executors.position_executor.data_types import TripleBarrierConf
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevel
from hummingbot.smart_components.strategy_frameworks.directional_trading.directional_trading_backtesting_engine import (
    DirectionalTradingBacktestingEngine,
)


class TestDirectionalTradingBacktestingEngine(unittest.TestCase):
    def get_controller_mock_simple(self):
        controller_base_mock = Mock()
        controller_base_mock.config.order_levels = [
            OrderLevel(level=1, side=TradeType.BUY, order_amount_usd=Decimal("10"),
                       triple_barrier_conf=TripleBarrierConf(take_profit=Decimal("0.2"),
                                                             stop_loss=Decimal("0.1"),
                                                             time_limit=360)),
            OrderLevel(level=1, side=TradeType.SELL, order_amount_usd=Decimal("10"),
                       triple_barrier_conf=TripleBarrierConf(take_profit=Decimal("0.2"),
                                                             stop_loss=Decimal("0.1"),
                                                             time_limit=360))
        ]
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

        controller_base_mock.get_processed_data = Mock(return_value=pd.DataFrame({
            "timestamp": timestamps,
            "close": [100, 110, 110, 130, 100],
            "signal": [1, 1, -1, -1, 1]
        }))
        return controller_base_mock

    def get_controller_mock_with_cooldown(self):
        controller_base_mock = Mock()
        controller_base_mock.config.order_levels = [
            OrderLevel(level=1, side=TradeType.BUY, order_amount_usd=Decimal("10"),
                       cooldown_time=60,
                       triple_barrier_conf=TripleBarrierConf(take_profit=Decimal("0.2"),
                                                             stop_loss=Decimal("0.1"),
                                                             time_limit=360)
                       ),
            OrderLevel(level=1, side=TradeType.SELL, order_amount_usd=Decimal("10"),
                       cooldown_time=60,
                       triple_barrier_conf=TripleBarrierConf(take_profit=Decimal("0.2"),
                                                             stop_loss=Decimal("0.1"),
                                                             time_limit=360))
        ]
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

        controller_base_mock.get_processed_data = Mock(return_value=pd.DataFrame({
            "timestamp": timestamps,
            "close": [100, 110, 110, 130, 100],
            "signal": [1, 1, -1, -1, 1]
        }))
        return controller_base_mock

    def test_run_backtesting_all_positions(self):
        engine = DirectionalTradingBacktestingEngine(self.get_controller_mock_simple())
        backtesting_results = engine.run_backtesting()
        self.assertIsInstance(backtesting_results, dict)
        processed_data = backtesting_results["processed_data"]
        self.assertIn("signal", processed_data.columns)

        executors_df = backtesting_results["executors_df"]
        self.assertIn("side", executors_df.columns)
        self.assertEqual(4, len(executors_df))
        self.assertEqual(2, len(executors_df[executors_df["profitable"] == 1]))

    def test_run_backtesting_with_cooldown(self):
        engine = DirectionalTradingBacktestingEngine(self.get_controller_mock_with_cooldown())
        backtesting_results = engine.run_backtesting()
        executors_df = backtesting_results["executors_df"]
        self.assertEqual(2, len(executors_df))
