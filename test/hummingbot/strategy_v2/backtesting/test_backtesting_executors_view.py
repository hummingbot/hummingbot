"""The controller's view of the executors must stay bounded while the run ledger stays complete.

Handing the controller every executor ever created makes a run quadratic in the number of
executors (each tick copies a list that only grows), so the engine exposes a time-bounded
window of terminated executors instead. The ledger that ``simulate_execution`` returns — the
one the results are summarized from — must keep every single executor regardless.
"""
import unittest
from decimal import Decimal
from unittest.mock import MagicMock

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class _FakeSimulation:
    """Minimal stand-in for an ExecutorSimulation that terminates at a fixed timestamp."""

    def __init__(self, executor_id: str, start: float, close_timestamp: float,
                 close_type: CloseType = CloseType.TAKE_PROFIT):
        self.config = PositionExecutorConfig(
            id=executor_id, timestamp=start,
            connector_name="binance", trading_pair="ETH-USDT",
            side=TradeType.BUY, amount=Decimal("1"),
            triple_barrier_config=TripleBarrierConfig(take_profit=Decimal("0.01")),
        )
        self.close_timestamp = close_timestamp
        self.close_type = close_type

    def get_executor_info_at_timestamp(self, timestamp: float) -> ExecutorInfo:
        is_done = timestamp >= self.close_timestamp
        return ExecutorInfo(
            id=self.config.id, timestamp=self.config.timestamp, type="position_executor",
            status=RunnableStatus.TERMINATED if is_done else RunnableStatus.RUNNING,
            config=self.config,
            net_pnl_pct=Decimal("0"), net_pnl_quote=Decimal("1"),
            cum_fees_quote=Decimal("0"), filled_amount_quote=Decimal("100"),
            is_active=not is_done, is_trading=not is_done,
            custom_info={"side": TradeType.BUY, "close_price": 1, "level_id": "buy_0"},
            close_timestamp=self.close_timestamp if is_done else None,
            close_type=self.close_type if is_done else None,
        )


class TestControllerExecutorsView(unittest.TestCase):
    WINDOW = 600.0  # seconds of terminated history the controller gets to see

    def _engine(self, window=WINDOW):
        engine = BacktestingEngineBase(terminated_executors_window=window)
        engine.controller = MagicMock()
        return engine

    @staticmethod
    def _run_ticks(engine, n_ticks: int, close_type: CloseType = CloseType.TAKE_PROFIT,
                   tick_seconds: float = 60.0):
        """Create one executor per tick that terminates on the next tick."""
        max_view_len = 0
        for tick in range(n_ticks):
            now = 1000.0 + tick * tick_seconds
            engine.active_executor_simulations.append(
                _FakeSimulation(f"executor_{tick}", start=now,
                                close_timestamp=now + tick_seconds, close_type=close_type))
            engine.update_executors_info(timestamp=now)
            engine._update_positions_from_stopped_executors()
            max_view_len = max(max_view_len, len(engine.controller.executors_info))
        return max_view_len

    def test_controller_view_is_bounded_while_ledger_stays_complete(self):
        engine = self._engine()
        n_ticks = 200

        max_view_len = self._run_ticks(engine, n_ticks)

        # One executor terminates per tick, so the whole run creates n_ticks - 1 terminated ones.
        self.assertEqual(len(engine.stopped_executors_info), n_ticks - 1)
        # The ledger returned to the caller keeps every one of them, plus the still-running one.
        self.assertEqual(len(engine.collect_executors_ledger()), n_ticks)
        # The controller only ever sees the active executor plus the last WINDOW seconds of them
        # (a 600s window at one termination every 60s covers 11 of them, both ends included).
        self.assertLessEqual(max_view_len, 1 + self.WINDOW / 60 + 1)
        self.assertLess(max_view_len, n_ticks)

    def test_view_keeps_the_whole_window_and_nothing_older(self):
        engine = self._engine()

        self._run_ticks(engine, 200)

        view = engine.controller.executors_info
        terminated = [executor for executor in view if executor.is_done]
        # Every terminated executor still inside the window is there, in termination order.
        self.assertEqual(len(terminated), self.WINDOW / 60 + 1)
        last_timestamp = 1000.0 + 199 * 60.0
        self.assertTrue(all(e.close_timestamp >= last_timestamp - self.WINDOW for e in terminated))
        self.assertEqual([e.id for e in terminated], sorted((e.id for e in terminated),
                                                            key=lambda i: int(i.split("_")[1])))

    def test_position_hold_executors_stay_in_the_view(self):
        """A filled maker order terminates as POSITION_HOLD, and that is the event a market
        maker's cooldown keys off before re-quoting the level — so the view must keep them,
        bounded by the window like any other close type."""
        engine = self._engine()

        self._run_ticks(engine, 50, close_type=CloseType.POSITION_HOLD)

        self.assertEqual(len(engine.stopped_executors_info), 49)
        self.assertEqual(len(engine.active_position_holds), 1)
        terminated = [e for e in engine.controller.executors_info if e.is_done]
        self.assertEqual(len(terminated), self.WINDOW / 60 + 1)
        self.assertTrue(all(e.close_type == CloseType.POSITION_HOLD for e in terminated))

    def test_window_none_restores_the_full_history(self):
        engine = self._engine(window=None)
        n_ticks = 50

        max_view_len = self._run_ticks(engine, n_ticks)

        self.assertEqual(max_view_len, n_ticks)
        self.assertEqual(len(engine.controller.executors_info), n_ticks)

    def test_default_window_is_used_when_not_specified(self):
        engine = BacktestingEngineBase()
        self.assertEqual(engine.terminated_executors_window,
                         BacktestingEngineBase.DEFAULT_TERMINATED_EXECUTORS_WINDOW)


if __name__ == "__main__":
    unittest.main()
