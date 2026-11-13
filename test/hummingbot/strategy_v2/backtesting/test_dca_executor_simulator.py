import unittest
from decimal import Decimal

import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.backtesting.executors_simulator.dca_executor_simulator import DCAExecutorSimulator
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.strategy_v2.models.executors import CloseType


def _make_df(closes):
    timestamps = [1000.0 + i * 60 for i in range(len(closes))]
    df = pd.DataFrame({"timestamp": timestamps, "close": closes, "low": closes, "high": closes})
    df.index = df["timestamp"]
    return df


class TestDCAExecutorSimulatorWithoutStopLoss(unittest.TestCase):
    """Regression tests for GitHub #8523: omitting stop_loss used to make the
    level-advance logic index past the last configured DCA level."""

    def test_runs_through_final_level_without_raising(self):
        config = DCAExecutorConfig(
            timestamp=1000.0,
            connector_name="binance",
            trading_pair="BTC-USDT",
            side=TradeType.BUY,
            amounts_quote=[Decimal("100"), Decimal("100")],
            prices=[Decimal("100"), Decimal("90")],
            stop_loss=None,
        )
        # Price walks down through both levels and keeps falling past the last one,
        # with no take_profit/trailing_stop configured to end the simulation first.
        df = _make_df([100, 95, 90, 85, 80, 75])

        simulator = DCAExecutorSimulator()
        simulation = simulator.simulate(df, config, trade_cost=0.0)

        self.assertEqual(simulation.close_type, CloseType.TIME_LIMIT)
        self.assertEqual(simulation.executor_simulation["timestamp"].max(), 1300.0)


if __name__ == "__main__":
    unittest.main()
