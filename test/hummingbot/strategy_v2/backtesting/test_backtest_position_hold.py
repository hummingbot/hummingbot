"""
Unit tests for BacktestPositionHold and position hold support in the backtesting engine.
"""
import unittest
from decimal import Decimal
from unittest.mock import MagicMock

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase, BacktestPositionHold
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


def _make_executor_info(exec_id="exec_1", side=TradeType.BUY,
                        filled_amount_quote=Decimal("1000"),
                        cum_fees_quote=Decimal("0.6"),
                        net_pnl_quote=Decimal("10"),
                        close_type=CloseType.POSITION_HOLD):
    config = PositionExecutorConfig(
        id=exec_id, timestamp=1000.0,
        connector_name="binance_perpetual", trading_pair="ETH-USDT",
        side=side, amount=Decimal("1"),
        triple_barrier_config=TripleBarrierConfig(
            stop_loss=Decimal("0.03"), take_profit=Decimal("0.02"), time_limit=2700),
    )
    return ExecutorInfo(
        id=exec_id, timestamp=1000.0, type="position_executor",
        status=RunnableStatus.TERMINATED, config=config,
        net_pnl_pct=Decimal("0.01"), net_pnl_quote=net_pnl_quote,
        cum_fees_quote=cum_fees_quote, filled_amount_quote=filled_amount_quote,
        is_active=False, is_trading=False,
        custom_info={"side": side, "close_price": 101.0,
                     "current_position_average_price": 100.0, "level_id": None},
        close_type=close_type,
    )


class TestBacktestPositionHold(unittest.TestCase):

    def test_initial_state(self):
        ph = BacktestPositionHold("binance_perpetual", "ETH-USDT")
        self.assertTrue(ph.is_closed)  # No amounts → net is 0 → closed
        self.assertEqual(ph.buy_amount_base, Decimal("0"))
        self.assertEqual(ph.sell_amount_base, Decimal("0"))

    def test_add_buy_executor(self):
        ph = BacktestPositionHold("binance_perpetual", "ETH-USDT")
        executor = _make_executor_info(side=TradeType.BUY)
        ph.add_executor(executor, entry_price=Decimal("100"))
        self.assertEqual(ph.buy_amount_base, Decimal("10"))  # 1000/100
        self.assertEqual(ph.buy_amount_quote, Decimal("1000"))
        self.assertEqual(ph.sell_amount_base, Decimal("0"))
        self.assertFalse(ph.is_closed)
        self.assertEqual(ph.net_amount_base, Decimal("10"))

    def test_add_sell_executor(self):
        ph = BacktestPositionHold("binance_perpetual", "ETH-USDT")
        executor = _make_executor_info(side=TradeType.SELL)
        ph.add_executor(executor, entry_price=Decimal("100"))
        self.assertEqual(ph.sell_amount_base, Decimal("10"))
        self.assertEqual(ph.net_amount_base, Decimal("-10"))

    def test_buy_sell_netting(self):
        """Buy and sell of same asset should reduce the position."""
        ph = BacktestPositionHold("binance_perpetual", "ETH-USDT")

        buy_exec = _make_executor_info("exec_buy", TradeType.BUY, Decimal("1000"))
        ph.add_executor(buy_exec, Decimal("100"))  # 10 base

        sell_exec = _make_executor_info("exec_sell", TradeType.SELL, Decimal("500"))
        ph.add_executor(sell_exec, Decimal("100"))  # 5 base

        self.assertEqual(ph.net_amount_base, Decimal("5"))  # 10 - 5
        self.assertFalse(ph.is_closed)

    def test_full_netting_closes_position(self):
        """Equal buy and sell should close the position."""
        ph = BacktestPositionHold("binance_perpetual", "ETH-USDT")

        buy_exec = _make_executor_info("exec_buy", TradeType.BUY, Decimal("1000"))
        ph.add_executor(buy_exec, Decimal("100"))

        sell_exec = _make_executor_info("exec_sell", TradeType.SELL, Decimal("1000"))
        ph.add_executor(sell_exec, Decimal("100"))

        self.assertEqual(ph.net_amount_base, Decimal("0"))
        self.assertTrue(ph.is_closed)

    def test_position_summary_long_profit(self):
        ph = BacktestPositionHold("binance_perpetual", "ETH-USDT")
        buy_exec = _make_executor_info("exec_buy", TradeType.BUY, Decimal("2000"))
        ph.add_executor(buy_exec, Decimal("200"))  # 10 base at 200

        summary = ph.get_position_summary(Decimal("220"))
        self.assertEqual(summary.side, TradeType.BUY)
        self.assertEqual(summary.amount, Decimal("10"))
        self.assertEqual(summary.breakeven_price, Decimal("200"))
        # unrealized = (220 - 200) * 10 = 200
        self.assertEqual(summary.unrealized_pnl_quote, Decimal("200"))
        self.assertEqual(summary.realized_pnl_quote, Decimal("0"))

    def test_position_summary_with_netting_realized_pnl(self):
        """Matched buy/sell should produce realized PnL."""
        ph = BacktestPositionHold("binance_perpetual", "ETH-USDT")

        buy_exec = _make_executor_info("exec_buy", TradeType.BUY, Decimal("1000"))
        ph.add_executor(buy_exec, Decimal("100"))  # 10 base at 100

        sell_exec = _make_executor_info("exec_sell", TradeType.SELL, Decimal("550"))
        ph.add_executor(sell_exec, Decimal("110"))  # 5 base at 110

        summary = ph.get_position_summary(Decimal("105"))
        # matched = min(10, 5) = 5 base
        # realized = (110 - 100) * 5 = 50
        self.assertEqual(summary.realized_pnl_quote, Decimal("50"))
        # net = 10 - 5 = 5 base, long
        self.assertEqual(summary.amount, Decimal("5"))
        self.assertEqual(summary.side, TradeType.BUY)
        # remaining buy: 5 base at 100 → breakeven = 500/5 = 100
        self.assertEqual(summary.breakeven_price, Decimal("100"))
        # unrealized = (105 - 100) * 5 = 25
        self.assertEqual(summary.unrealized_pnl_quote, Decimal("25"))

    def test_position_summary_short_unrealized(self):
        """Net short position should have correct unrealized PnL."""
        ph = BacktestPositionHold("binance_perpetual", "ETH-USDT")
        sell_exec = _make_executor_info("exec_sell", TradeType.SELL, Decimal("1000"))
        ph.add_executor(sell_exec, Decimal("100"))  # 10 base short

        summary = ph.get_position_summary(Decimal("95"))
        self.assertEqual(summary.side, TradeType.SELL)
        # unrealized = (100 - 95) * 10 = 50
        self.assertEqual(summary.unrealized_pnl_quote, Decimal("50"))


class TestSummarizeResultsWithPositionHolds(unittest.TestCase):

    def test_summarize_empty_with_unrealized(self):
        results = BacktestingEngineBase.summarize_results([], total_amount_quote=1000)
        self.assertEqual(results["unrealized_pnl_quote"], 0)

    def test_position_hold_executor_pnl_excluded(self):
        """POSITION_HOLD executor PnL should NOT be counted in net PnL."""
        executor = _make_executor_info(
            close_type=CloseType.POSITION_HOLD, net_pnl_quote=Decimal("10"))

        ph = BacktestPositionHold("binance_perpetual", "ETH-USDT")
        ph.add_executor(executor, Decimal("100"))

        results = BacktestingEngineBase.summarize_results(
            [executor], total_amount_quote=1000,
            position_holds=[ph], final_price=Decimal("100"),
        )
        # Executor PnL of 10 should be excluded; position at same price → 0 unrealized
        self.assertAlmostEqual(results["net_pnl_quote"], 0.0)

    def test_summarize_with_open_position_holds(self):
        """Position unrealized PnL should be reported."""
        executor = _make_executor_info(close_type=CloseType.POSITION_HOLD)

        ph = BacktestPositionHold("binance_perpetual", "ETH-USDT")
        ph.add_executor(executor, Decimal("100"))  # 10 base at 100

        results = BacktestingEngineBase.summarize_results(
            [executor], total_amount_quote=1000,
            position_holds=[ph], final_price=Decimal("110"),
        )
        # unrealized = (110 - 100) * 10 = 100
        self.assertAlmostEqual(results["unrealized_pnl_quote"], 100.0)
        self.assertIn("position_realized_pnl_quote", results)

    def test_netted_position_realized_pnl_in_summary(self):
        """Position realized PnL from netting should be in results."""
        buy_exec = _make_executor_info("buy_1", TradeType.BUY, Decimal("1000"),
                                       close_type=CloseType.POSITION_HOLD)
        sell_exec = _make_executor_info("sell_1", TradeType.SELL, Decimal("1000"),
                                        close_type=CloseType.POSITION_HOLD)

        ph = BacktestPositionHold("binance_perpetual", "ETH-USDT")
        ph.add_executor(buy_exec, Decimal("100"))   # 10 base at 100
        ph.add_executor(sell_exec, Decimal("110"))   # ~9.09 base at 110

        results = BacktestingEngineBase.summarize_results(
            [buy_exec, sell_exec], total_amount_quote=1000,
            position_holds=[ph], final_price=Decimal("105"),
        )
        # realized = (110 - 100) * min(10, 9.09) = ~90.9
        self.assertGreater(results["position_realized_pnl_quote"], 0)


class TestNaturalTerminationPositionHold(unittest.TestCase):
    """An executor that auto-terminates as POSITION_HOLD (e.g. an OrderExecutor whose
    maker order filled) must be routed to the position-hold ledger by update_executors_info,
    NOT booked as a realized-PnL close. Regression test for the OrderExecutor/King path."""

    def _engine_with_state(self):
        engine = BacktestingEngineBase()
        engine.controller = MagicMock()
        engine.active_executor_simulations = []
        engine.stopped_executors_info = []
        engine.active_position_holds = {}
        engine._position_hold_processed_ids = set()
        engine._pending_position_hold_executors = []
        engine._executor_realized_pnl = 0.0
        engine._cumulative_volume = 0.0
        return engine

    def _terminated_sim(self, close_type, filled_quote=Decimal("1000"), net_pnl=Decimal("0")):
        config = PositionExecutorConfig(
            id="order_1", timestamp=1000.0,
            connector_name="binance", trading_pair="WLD-FDUSD",
            side=TradeType.BUY, amount=Decimal("1"),
            triple_barrier_config=TripleBarrierConfig(take_profit=Decimal("0.01")),
        )
        info = ExecutorInfo(
            id="order_1", timestamp=1000.0, type="order_executor",
            status=RunnableStatus.TERMINATED, config=config,
            net_pnl_pct=Decimal("0"), net_pnl_quote=net_pnl,
            cum_fees_quote=Decimal("0"), filled_amount_quote=filled_quote,
            is_active=False, is_trading=False,
            custom_info={"side": TradeType.BUY, "current_position_average_price": 0.5,
                         "close_price": 0.5, "level_id": "buy_0"},
            close_type=close_type,
        )
        sim = MagicMock()
        sim.config = config
        sim.get_executor_info_at_timestamp = MagicMock(return_value=info)
        return sim

    def test_position_hold_termination_is_enqueued_not_realized(self):
        engine = self._engine_with_state()
        engine.active_executor_simulations = [self._terminated_sim(CloseType.POSITION_HOLD)]

        engine.update_executors_info(timestamp=2000.0)

        # Routed to the pending position-hold queue, not booked as realized PnL.
        self.assertEqual(len(engine._pending_position_hold_executors), 1)
        self.assertEqual(engine._executor_realized_pnl, 0.0)
        self.assertEqual(engine._cumulative_volume, 1000.0)

        # Draining the queue creates an actual position hold with the filled amount.
        engine._update_positions_from_stopped_executors()
        self.assertEqual(len(engine.active_position_holds), 1)
        ph = next(iter(engine.active_position_holds.values()))
        self.assertEqual(ph.buy_amount_quote, Decimal("1000"))
        self.assertFalse(ph.is_closed)

    def test_tp_termination_still_books_realized_pnl(self):
        engine = self._engine_with_state()
        engine.active_executor_simulations = [
            self._terminated_sim(CloseType.TAKE_PROFIT, net_pnl=Decimal("12"))
        ]

        engine.update_executors_info(timestamp=2000.0)

        # Non-hold natural termination still counts as realized PnL, no position hold.
        self.assertEqual(len(engine._pending_position_hold_executors), 0)
        self.assertEqual(engine._executor_realized_pnl, 12.0)


if __name__ == "__main__":
    unittest.main()
