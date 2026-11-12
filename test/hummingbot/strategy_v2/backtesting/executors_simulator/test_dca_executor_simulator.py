import unittest
from decimal import Decimal

import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.backtesting.executors_simulator.dca_executor_simulator import DCAExecutorSimulator
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig


class TestDCAExecutorSimulator(unittest.TestCase):

    def test_each_stage_uses_its_own_entry_timestamp(self):
        timestamps = [1000.0, 1001.0, 1002.0, 1003.0, 1004.0]
        close_prices = [105.0, 100.0, 95.0, 90.0, 92.0]
        df = pd.DataFrame(
            {
                "timestamp": timestamps,
                "open": close_prices,
                "high": [price + 1 for price in close_prices],
                "low": [price - 1 for price in close_prices],
                "close": close_prices,
                "volume": [1.0] * len(timestamps),
            },
            index=timestamps,
        )
        config = DCAExecutorConfig(
            id="test",
            timestamp=timestamps[0],
            connector_name="binance",
            trading_pair="ETH-USDT",
            side=TradeType.BUY,
            amounts_quote=[Decimal("10"), Decimal("10")],
            prices=[Decimal("100"), Decimal("90")],
            stop_loss=Decimal("0.5"),
        )

        result = DCAExecutorSimulator().simulate(df, config, trade_cost=0).executor_simulation

        self.assertEqual(10.0, result.loc[1001.0, "filled_amount_quote_0"])
        self.assertEqual(0.0, result.loc[1001.0, "filled_amount_quote_1"])
        self.assertEqual(10.0, result.loc[1003.0, "filled_amount_quote_0"])
        self.assertEqual(10.0, result.loc[1003.0, "filled_amount_quote_1"])
