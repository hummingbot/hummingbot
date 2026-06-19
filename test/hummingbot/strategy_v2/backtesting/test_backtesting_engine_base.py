
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pandas as pd

from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

from hummingbot.strategy_v2.backtesting.backtesting_engine_base import BacktestingEngineBase
from hummingbot.strategy_v2.models.executor_actions import StopExecutorAction


class TestBacktestingEngineBase(IsolatedAsyncioWrapperTestCase):

    async def test_simulate_execution_refreshes_controller_processed_data_each_tick(self):
        engine = BacktestingEngineBase()
        engine.backtesting_data_provider._resolve_connector_name = MagicMock(return_value="binance_perpetual")
        engine.prepare_market_data = MagicMock(
            return_value=pd.DataFrame([
                {"timestamp": 1.0, "close_bt": "100"},
                {"timestamp": 2.0, "close_bt": "101"},
            ])
        )

        class DummyMarketDataProvider:
            def __init__(self):
                self.prices = {}
                self._time = None

        class DummyController:
            def __init__(self):
                self.config = SimpleNamespace(
                    id="test-controller",
                    connector_name="binance_perpetual",
                    trading_pair="ETH-USDT",
                    total_amount_quote=Decimal("100"),
                )
                self.market_data_provider = DummyMarketDataProvider()
                self.processed_data = {"close_to_mean": False}
                self.executors_info = []
                self.positions_held = []
                self._update_processed_data_calls = 0
                self.update_processed_data = AsyncMock(side_effect=self._update_processed_data)

            async def _update_processed_data(self):
                self._update_processed_data_calls += 1
                key = "binance_perpetual_ETH-USDT"
                self.processed_data["close_to_mean"] = self.market_data_provider.prices[key] >= Decimal("101")

            def stop_actions_proposal(self):
                if not self.processed_data.get("close_to_mean", False):
                    return []
                return [StopExecutorAction(controller_id=self.config.id, executor_id="executor-1")]

            def determine_executor_actions(self):
                return self.stop_actions_proposal()

        engine.controller = DummyController()
        engine.handle_stop_action = MagicMock()

        await engine.simulate_execution(trade_cost=0.0)

        self.assertEqual(engine.controller.update_processed_data.await_count, 2)
        self.assertEqual(engine.controller._update_processed_data_calls, 2)
        self.assertEqual(engine.handle_stop_action.call_count, 1)
        self.assertEqual(engine.decision_trace[-1]["action_types"], "StopExecutorAction")
