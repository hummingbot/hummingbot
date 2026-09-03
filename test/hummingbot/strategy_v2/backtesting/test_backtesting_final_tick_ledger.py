"""What the controller does on the closing tick has to reach the results.

``update_executors_info()`` runs at the *start* of a tick, so anything
``determine_executor_actions()`` does on the last one happens after the engine's last look at
the executors. The ledger returned by ``simulate_execution()`` is therefore rebuilt from the
live simulations rather than replayed from that stale look.
"""
import unittest
from decimal import Decimal
from unittest.mock import MagicMock

import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase
from hummingbot.strategy_v2.backtesting.executor_simulator_base import ExecutorSimulation
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors import CloseType

TICKS = [0.0, 60.0, 120.0]


def _config(executor_id: str, timestamp: float) -> PositionExecutorConfig:
    return PositionExecutorConfig(
        id=executor_id, timestamp=timestamp,
        connector_name="binance", trading_pair="ETH-USDT",
        side=TradeType.BUY, amount=Decimal("1"), entry_price=Decimal("100"),
        triple_barrier_config=TripleBarrierConfig(take_profit=Decimal("0.01")),
        level_id="buy_0",
    )


def _simulation(config: PositionExecutorConfig, timestamps, close_type=CloseType.TIME_LIMIT,
                net_pnl_quote=Decimal("3")) -> ExecutorSimulation:
    df = pd.DataFrame({
        "net_pnl_pct": [0.03] * len(timestamps),
        "net_pnl_quote": [float(net_pnl_quote)] * len(timestamps),
        "cum_fees_quote": [0.1] * len(timestamps),
        "filled_amount_quote": [100.0] * len(timestamps),
        "close": [100.0] * len(timestamps),
    }, index=pd.Index(timestamps, name="timestamp"))
    return ExecutorSimulation(config=config, executor_simulation=df, close_type=close_type)


def _order_config(executor_id: str, timestamp: float) -> OrderExecutorConfig:
    return OrderExecutorConfig(
        id=executor_id, timestamp=timestamp,
        connector_name="binance", trading_pair="ETH-USDT",
        side=TradeType.BUY, amount=Decimal("1"), price=Decimal("100"),
        execution_strategy=ExecutionStrategy.MARKET,
        level_id="buy_0",
    )


def _hold_simulation(config: OrderExecutorConfig, timestamps, entry_price=100.0) -> ExecutorSimulation:
    """A maker order that fills and keeps the position: terminates as POSITION_HOLD."""
    df = pd.DataFrame({
        "net_pnl_pct": [0.0] * len(timestamps),
        "net_pnl_quote": [0.0] * len(timestamps),
        "cum_fees_quote": [0.0] * len(timestamps),
        "filled_amount_quote": [entry_price] * len(timestamps),
        "current_position_average_price": [entry_price] * len(timestamps),
        "close": [entry_price] * len(timestamps),
    }, index=pd.Index(timestamps, name="timestamp"))
    return ExecutorSimulation(config=config, executor_simulation=df, close_type=CloseType.POSITION_HOLD)


def _features() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": TICKS,
        "close_bt": [100.0] * len(TICKS),
    }, index=pd.Index(TICKS, name="timestamp"))


class _ScriptedController:
    """Controller that emits a scripted list of actions per tick."""

    def __init__(self, actions_by_tick):
        self._actions_by_tick = actions_by_tick
        self.config = MagicMock(connector_name="binance", trading_pair="ETH-USDT", id="test")
        self.market_data_provider = MagicMock()
        self.processed_data = {}
        self.executors_info = []
        self.positions_held = []

    def determine_executor_actions(self):
        return self._actions_by_tick.get(self.processed_data["timestamp"], [])


class TestFinalTickLedger(unittest.IsolatedAsyncioTestCase):

    @staticmethod
    def _engine(controller, simulations_by_id):
        engine = BacktestingEngineBase()
        engine.controller = controller
        engine.prepare_market_data = MagicMock(return_value=_features())
        engine.simulate_executor = MagicMock(
            side_effect=lambda config, df, trade_cost: simulations_by_id[config.id])
        return engine

    async def test_executor_created_on_the_final_tick_reaches_the_ledger(self):
        """The last tick's CreateExecutorAction lands after update_executors_info() has run."""
        early, late = _config("early", 60.0), _config("late", 120.0)
        controller = _ScriptedController({
            60.0: [CreateExecutorAction(controller_id="test", executor_config=early)],
            120.0: [CreateExecutorAction(controller_id="test", executor_config=late)],
        })
        engine = self._engine(controller, {
            "early": _simulation(early, [60.0, 120.0]),
            "late": _simulation(late, [120.0], net_pnl_quote=Decimal("7")),
        })

        ledger = await engine.simulate_execution(trade_cost=0.0)

        self.assertEqual(sorted(executor.id for executor in ledger), ["early", "late"])
        late_info = next(executor for executor in ledger if executor.id == "late")
        self.assertEqual(late_info.status, RunnableStatus.TERMINATED)
        self.assertEqual(late_info.net_pnl_quote, Decimal("7"))
        # And the results summarize the executor that would otherwise have gone missing.
        results = BacktestingEngineBase.summarize_results(
            ledger, total_amount_quote=1000, pnl_timeseries=engine.pnl_timeseries)
        self.assertEqual(results["total_executors"], 2)
        self.assertEqual(results["net_pnl_quote"], 10.0)

    async def test_no_executor_is_counted_twice(self):
        """A simulation lives either in active_executor_simulations or in stopped_executors_info."""
        early, late = _config("early", 60.0), _config("late", 120.0)
        controller = _ScriptedController({
            60.0: [CreateExecutorAction(controller_id="test", executor_config=early)],
            120.0: [CreateExecutorAction(controller_id="test", executor_config=late)],
        })
        engine = self._engine(controller, {
            "early": _simulation(early, [60.0, 120.0]),
            "late": _simulation(late, [120.0]),
        })

        ledger = await engine.simulate_execution(trade_cost=0.0)

        ids = [executor.id for executor in ledger]
        self.assertEqual(len(ids), len(set(ids)))

    async def test_running_totals_and_ledger_agree_on_the_booked_executors(self):
        """Every executor booked into the running totals is in the ledger with its close info."""
        early, late = _config("early", 60.0), _config("late", 120.0)
        controller = _ScriptedController({
            60.0: [CreateExecutorAction(controller_id="test", executor_config=early)],
            120.0: [CreateExecutorAction(controller_id="test", executor_config=late)],
        })
        engine = self._engine(controller, {
            "early": _simulation(early, [60.0, 120.0]),
            "late": _simulation(late, [120.0]),
        })

        ledger = await engine.simulate_execution(trade_cost=0.0)

        booked_ids = {executor.id for executor in engine.stopped_executors_info}
        ledger_by_id = {executor.id: executor for executor in ledger}
        self.assertTrue(booked_ids.issubset(ledger_by_id))
        for executor_id in booked_ids:
            self.assertEqual(ledger_by_id[executor_id].status, RunnableStatus.TERMINATED)
            self.assertIsNotNone(ledger_by_id[executor_id].close_type)

    async def test_position_hold_created_on_the_final_tick_is_accounted_for(self):
        """A maker order created and filled on the closing tick keeps its position, so it has to
        go through position-hold accounting rather than land in the ledger unaccounted for."""
        late = _order_config("late_hold", 120.0)
        controller = _ScriptedController({
            120.0: [CreateExecutorAction(controller_id="test", executor_config=late)],
        })
        engine = self._engine(controller, {"late_hold": _hold_simulation(late, [120.0])})

        ledger = await engine.simulate_execution(trade_cost=0.0)

        self.assertEqual([executor.id for executor in ledger], ["late_hold"])
        self.assertEqual(ledger[0].close_type, CloseType.POSITION_HOLD)

        # Its exposure reaches the position-hold ledger...
        holds = list(engine.active_position_holds.values())
        self.assertEqual(len(holds), 1)
        self.assertEqual(holds[0].net_amount_base, Decimal("1"))
        self.assertEqual(holds[0].volume_traded_quote, Decimal("100"))
        # ...and the fill is not silently dropped from the summary: a POSITION_HOLD executor is
        # excluded from the executor PnL, so without the hold its 100 quote of volume vanished.
        results = BacktestingEngineBase.summarize_results(
            ledger, total_amount_quote=1000,
            position_holds=holds, final_price=Decimal("110"),
            pnl_timeseries=engine.pnl_timeseries)
        self.assertEqual(results["unrealized_pnl_quote"], 10.0)

    def test_executor_stopped_after_the_last_look_keeps_its_terminated_info(self):
        """A StopExecutorAction handled after update_executors_info() must win over the stale
        running snapshot the controller was holding."""
        engine = BacktestingEngineBase()
        engine.controller = MagicMock()
        config = _config("stopped_late", 60.0)
        engine.active_executor_simulations = [_simulation(config, [60.0, 120.0, 180.0])]

        # The engine's last look at the executors: still running at t=120.
        engine.update_executors_info(timestamp=120.0)
        self.assertEqual(engine.controller.executors_info[0].status, RunnableStatus.RUNNING)

        # ...and only afterwards does the controller ask for it to be stopped.
        engine.handle_stop_action(
            StopExecutorAction(controller_id="test", executor_id="stopped_late"), timestamp=120.0)

        ledger = engine.collect_executors_ledger(120.0)
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0].status, RunnableStatus.TERMINATED)
        self.assertEqual(ledger[0].close_type, CloseType.EARLY_STOP)
        self.assertEqual(ledger[0].close_timestamp, 120.0)


if __name__ == "__main__":
    unittest.main()
