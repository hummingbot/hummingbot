import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.smart_components.strategy_frameworks.data_types import OrderLevel, TripleBarrierConf
from hummingbot.smart_components.strategy_frameworks.directional_trading.directional_trading_backtesting_engine import (
    DirectionalTradingBacktestingEngine,
)


class TestDirectionalTradingBacktestingEngine(unittest.TestCase):

    def setUp(self):
        self.controller_mock = Mock()
        self.controller_mock.config.order_levels = [
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

        self.controller_mock.get_processed_data = Mock(return_value=pd.DataFrame({
            "timestamp": timestamps,
            "close": [100, 110, 110, 130, 100],
            "signal": [1, 1, -1, -1, 1]
        }))
        self.engine = DirectionalTradingBacktestingEngine(self.controller_mock)

    def test_run_backtesting(self):
        backtesting_results = self.engine.run_backtesting()
        self.assertIsInstance(backtesting_results, dict)
        self.assertIn("signal", backtesting_results["processed_data"].columns)
