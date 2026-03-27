"""Tests for PositionExecutorSimulator using config.entry_price (Issue #8142)."""
import unittest
from decimal import Decimal

import pandas as pd

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.strategy_v2.backtesting.executors_simulator.position_executor_simulator import PositionExecutorSimulator
from hummingbot.strategy_v2.executors.position_executor.data_types import (
    PositionExecutorConfig,
    TripleBarrierConfig,
)


class TestPositionExecutorSimulatorEntryPrice(unittest.TestCase):
    """Tests for PositionExecutorSimulator using config.entry_price (Issue #8142)."""

    def _make_df(self, timestamps, closes, lows=None, highs=None):
        """Build a synthetic OHLCV DataFrame indexed by timestamp."""
        n = len(timestamps)
        if lows is None:
            lows = [c * 0.99 for c in closes]
        if highs is None:
            highs = [c * 1.01 for c in closes]
        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': closes,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': [100.0] * n,
        })
        df.index = df['timestamp']
        return df

    def test_pnl_uses_config_entry_price_not_first_close(self):
        """
        When config.entry_price=100 but first close=105, the PnL should be based on
        entry_price=100, not 105.
        """
        timestamps = [1000.0, 2000.0, 3000.0]
        closes = [105.0, 108.0, 110.0]
        df = self._make_df(timestamps, closes)

        config = PositionExecutorConfig(
            timestamp=1000.0,
            trading_pair='BTC-USDT',
            connector_name='binance',
            side=TradeType.BUY,
            entry_price=Decimal('100'),
            amount=Decimal('1'),
            triple_barrier_config=TripleBarrierConfig(
                open_order_type=OrderType.MARKET,
            ),
        )

        simulator = PositionExecutorSimulator()
        result = simulator.simulate(df, config, trade_cost=0.0)
        sim_df = result.executor_simulation

        # At the last row (close=110), PnL should be (110/100 - 1) = 0.10
        last_pnl = sim_df['net_pnl_pct'].iloc[-1]
        self.assertAlmostEqual(last_pnl, 0.10, places=6,
                               msg=f'Expected PnL 0.10, got {last_pnl}')

        # At the first row (close=105), PnL should be (105/100 - 1) = 0.05
        first_pnl = sim_df['net_pnl_pct'].iloc[0]
        self.assertAlmostEqual(first_pnl, 0.05, places=6,
                               msg=f'Expected PnL 0.05, got {first_pnl}')

    def test_pnl_short_side_uses_config_entry_price(self):
        """For a SHORT trade, PnL = -(close/entry_price - 1), using config.entry_price."""
        timestamps = [1000.0, 2000.0, 3000.0]
        closes = [100.0, 95.0, 90.0]
        df = self._make_df(timestamps, closes)

        config = PositionExecutorConfig(
            timestamp=1000.0,
            trading_pair='BTC-USDT',
            connector_name='binance',
            side=TradeType.SELL,
            entry_price=Decimal('100'),
            amount=Decimal('1'),
            triple_barrier_config=TripleBarrierConfig(
                open_order_type=OrderType.MARKET,
            ),
        )

        simulator = PositionExecutorSimulator()
        result = simulator.simulate(df, config, trade_cost=0.0)
        sim_df = result.executor_simulation

        # At close=90, PnL for SHORT = -(90/100 - 1) = 0.10
        last_pnl = sim_df['net_pnl_pct'].iloc[-1]
        self.assertAlmostEqual(last_pnl, 0.10, places=6,
                               msg=f'Expected PnL 0.10 for short, got {last_pnl}')

    def test_filled_amount_quote_uses_config_entry_price(self):
        """filled_amount_quote should be amount * entry_price from config."""
        timestamps = [1000.0, 2000.0]
        closes = [105.0, 110.0]
        df = self._make_df(timestamps, closes)

        config = PositionExecutorConfig(
            timestamp=1000.0,
            trading_pair='BTC-USDT',
            connector_name='binance',
            side=TradeType.BUY,
            entry_price=Decimal('100'),
            amount=Decimal('2'),
            triple_barrier_config=TripleBarrierConfig(
                open_order_type=OrderType.MARKET,
            ),
        )

        simulator = PositionExecutorSimulator()
        result = simulator.simulate(df, config, trade_cost=0.0)
        sim_df = result.executor_simulation

        # filled_amount_quote at first row should be amount * entry_price = 2 * 100 = 200
        self.assertAlmostEqual(sim_df['filled_amount_quote'].iloc[0], 200.0, places=2)


if __name__ == '__main__':
    unittest.main()
