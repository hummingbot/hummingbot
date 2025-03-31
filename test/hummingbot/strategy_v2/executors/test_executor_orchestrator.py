import unittest
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, patch

from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.arbitrage_executor.arbitrage_executor import ArbitrageExecutor
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.strategy_v2.executors.dca_executor.dca_executor import DCAExecutor
from hummingbot.strategy_v2.executors.executor_orchestrator import ExecutorOrchestrator, PositionHold
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig
from hummingbot.strategy_v2.executors.grid_executor.grid_executor import GridExecutor
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.executors.position_executor.position_executor import PositionExecutor
from hummingbot.strategy_v2.executors.twap_executor.data_types import TWAPExecutorConfig
from hummingbot.strategy_v2.executors.twap_executor.twap_executor import TWAPExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction, StoreExecutorAction
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo, PerformanceReport


class TestExecutorOrchestrator(unittest.TestCase):

    @patch.object(MarketsRecorder, "get_instance")
    def setUp(self, markets_recorder: MagicMock):
        markets_recorder.return_value = MagicMock(spec=MarketsRecorder)
        markets_recorder.get_all_executors = MagicMock(return_value=[])
        markets_recorder.store_or_update_executor = MagicMock(return_value=None)
        self.mock_strategy = self.create_mock_strategy()
        self.orchestrator = ExecutorOrchestrator(strategy=self.mock_strategy)

    @staticmethod
    def create_mock_strategy():
        market = MagicMock()
        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock(spec=ScriptStrategyBase)
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="ETH-USDT")
        connector = MagicMock(spec=ExchangePyBase)
        type(connector).trading_rules = PropertyMock(return_value={"ETH-USDT": TradingRule(trading_pair="ETH-USDT")})
        strategy.connectors = {
            "binance": connector,
        }
        strategy.market_data_provider = MagicMock(spec=MarketDataProvider)
        strategy.market_data_provider.get_price_by_type = MagicMock(return_value=Decimal(230))
        return strategy

    @patch.object(PositionExecutor, "start")
    @patch.object(DCAExecutor, "start")
    @patch.object(ArbitrageExecutor, "start")
    @patch.object(TWAPExecutor, "start")
    @patch.object(GridExecutor, "start")
    @patch.object(GridExecutor, "_generate_grid_levels")
    @patch.object(MarketsRecorder, "get_instance")
    def test_execute_actions_create_executor(self, markets_recorder_mock, grid_start_mock: MagicMock,
                                             generate_grid_levels_mock: MagicMock,
                                             arbitrage_start_mock: MagicMock, dca_start_mock: MagicMock,
                                             position_start_mock: MagicMock, twap_start_mock: MagicMock):
        markets_recorder_mock.return_value = MagicMock(spec=MarketsRecorder)
        markets_recorder_mock.store_or_update_executor = MagicMock(return_value=None)
        position_executor_config = PositionExecutorConfig(
            timestamp=1234, connector_name="binance",
            trading_pair="ETH-USDT", side=TradeType.BUY, entry_price=Decimal(100), amount=Decimal(10))
        arbitrage_executor_config = ArbitrageExecutorConfig(
            timestamp=1234, order_amount=Decimal(10), min_profitability=Decimal(0.01),
            buying_market=ConnectorPair(connector_name="binance", trading_pair="ETH-USDT"),
            selling_market=ConnectorPair(connector_name="coinbase", trading_pair="ETH-USDT"),
        )
        dca_executor_config = DCAExecutorConfig(
            timestamp=1234, connector_name="binance", trading_pair="ETH-USDT",
            side=TradeType.BUY, amounts_quote=[Decimal(10)], prices=[Decimal(100)],)
        twap_executor_config = TWAPExecutorConfig(
            timestamp=1234, connector_name="binance", trading_pair="ETH-USDT",
            side=TradeType.BUY, total_amount_quote=Decimal(100), total_duration=10, order_interval=5,
        )
        grid_executor_config = GridExecutorConfig(
            timestamp=1234, connector_name="binance", trading_pair="ETH-USDT",
            side=TradeType.BUY, total_amount_quote=Decimal(100), start_price=Decimal(100),
            end_price=Decimal(200), limit_price=Decimal(90),
            triple_barrier_config=TripleBarrierConfig(take_profit=Decimal(0.01), stop_loss=Decimal(0.2))
        )
        actions = [
            CreateExecutorAction(executor_config=position_executor_config, controller_id="test"),
            CreateExecutorAction(executor_config=arbitrage_executor_config, controller_id="test"),
            CreateExecutorAction(executor_config=dca_executor_config, controller_id="test"),
            CreateExecutorAction(executor_config=twap_executor_config, controller_id="test"),
            CreateExecutorAction(executor_config=grid_executor_config, controller_id="test"),
        ]
        self.orchestrator.execute_actions(actions)
        self.assertEqual(len(self.orchestrator.active_executors["test"]), 5)

    def test_execute_actions_store_executor_active(self):
        position_executor = MagicMock(spec=PositionExecutor)
        position_executor.is_active = True
        config_mock = MagicMock(PositionExecutorConfig)
        config_mock.id = "test"
        config_mock.controller_id = "test"
        position_executor.config = config_mock
        self.orchestrator.cached_performance["test"] = PerformanceReport()
        self.orchestrator.active_executors["test"] = [position_executor]
        actions = [StoreExecutorAction(executor_id="test", controller_id="test")]
        self.orchestrator.execute_actions(actions)
        self.assertEqual(len(self.orchestrator.active_executors["test"]), 1)

    @patch.object(MarketsRecorder, "get_instance")
    def test_execute_actions_store_executor_inactive(self, markets_recorder_mock):
        markets_recorder_mock.return_value = MagicMock(spec=MarketsRecorder)
        markets_recorder_mock.store_or_update_executor = MagicMock(return_value=None)
        position_executor = MagicMock(spec=PositionExecutor)
        position_executor.is_active = False
        config_mock = MagicMock(PositionExecutorConfig)
        config_mock.id = "test"
        config_mock.controller_id = "test"
        position_executor.config = config_mock
        self.orchestrator.active_executors["test"] = [position_executor]
        self.orchestrator.archived_executors["test"] = []
        self.orchestrator.cached_performance["test"] = PerformanceReport()
        actions = [StoreExecutorAction(executor_id="test", controller_id="test")]
        self.orchestrator.execute_actions(actions)
        self.assertEqual(len(self.orchestrator.active_executors["test"]), 0)

    @patch('hummingbot.connector.markets_recorder.MarketsRecorder.get_instance')
    def test_generate_performance_report(self, mock_get_instance):
        # Create a mock for MarketsRecorder and its get_executors_by_controller method
        mock_markets_recorder = MagicMock(spec=MarketsRecorder)
        mock_markets_recorder.get_executors_by_controller.return_value = []
        mock_get_instance.return_value = mock_markets_recorder
        config_mock = PositionExecutorConfig(
            timestamp=1234, trading_pair="ETH-USDT", connector_name="binance",
            side=TradeType.BUY, amount=Decimal(10), entry_price=Decimal(100),
        )
        position_executor_non_active = MagicMock(spec=PositionExecutor)
        position_executor_non_active.executor_info = ExecutorInfo(
            id="123", timestamp=1234, type="position_executor",
            status=RunnableStatus.RUNNING, config=config_mock,
            filled_amount_quote=Decimal(0), net_pnl_quote=Decimal(0), net_pnl_pct=Decimal(0),
            cum_fees_quote=Decimal(0), is_trading=False, is_active=True, custom_info={"side": TradeType.BUY}
        )
        position_executor_active = MagicMock(spec=PositionExecutor)
        position_executor_active.executor_info = ExecutorInfo(
            id="123", timestamp=1234, type="position_executor",
            status=RunnableStatus.RUNNING, config=config_mock,
            filled_amount_quote=Decimal(100), net_pnl_quote=Decimal(10), net_pnl_pct=Decimal(10),
            cum_fees_quote=Decimal(1), is_trading=True, is_active=True, custom_info={"side": TradeType.BUY}
        )
        position_executor_failed = MagicMock(spec=PositionExecutor)
        position_executor_failed.executor_info = ExecutorInfo(
            id="123", timestamp=1234, type="position_executor",
            status=RunnableStatus.TERMINATED, config=config_mock,
            close_type=CloseType.FAILED,
            filled_amount_quote=Decimal(100), net_pnl_quote=Decimal(0), net_pnl_pct=Decimal(0),
            cum_fees_quote=Decimal(1), is_trading=True, is_active=True, custom_info={"side": TradeType.BUY}
        )
        position_executor_tp = MagicMock(spec=PositionExecutor)
        position_executor_tp.executor_info = ExecutorInfo(
            id="123", timestamp=1234, type="position_executor",
            status=RunnableStatus.TERMINATED, config=config_mock,
            close_type=CloseType.TAKE_PROFIT,
            filled_amount_quote=Decimal(100), net_pnl_quote=Decimal(10), net_pnl_pct=Decimal(10),
            cum_fees_quote=Decimal(1), is_trading=False, is_active=False, custom_info={"side": TradeType.BUY}
        )
        self.orchestrator.active_executors["test"] = [position_executor_non_active, position_executor_active,
                                                      position_executor_failed, position_executor_tp]
        report = self.orchestrator.generate_performance_report(controller_id="test")
        self.assertEqual(report.realized_pnl_quote, Decimal(10))
        self.assertEqual(report.unrealized_pnl_quote, Decimal(10))

    @patch("hummingbot.strategy_v2.executors.executor_orchestrator.MarketsRecorder.get_instance")
    def test_initialize_cached_performance(self, mock_get_instance: MagicMock):
        # Create mock markets recorder
        mock_markets_recorder = MagicMock(spec=MarketsRecorder)
        mock_get_instance.return_value = mock_markets_recorder

        # Create mock executor info
        executor_info = ExecutorInfo(
            id="123", timestamp=1234, type="position_executor",
            status=RunnableStatus.RUNNING, config=PositionExecutorConfig(
                timestamp=1234, trading_pair="ETH-USDT", connector_name="binance",
                side=TradeType.BUY, amount=Decimal(10), entry_price=Decimal(100),
            ),
            filled_amount_quote=Decimal(100), net_pnl_quote=Decimal(10), net_pnl_pct=Decimal(10),
            cum_fees_quote=Decimal(1), is_trading=True, is_active=True, custom_info={"side": TradeType.BUY},
            controller_id="test",
        )

        # Set up mock to return executor info
        mock_markets_recorder.get_all_executors.return_value = [executor_info]

        orchestrator = ExecutorOrchestrator(strategy=self.mock_strategy)
        self.assertEqual(len(orchestrator.cached_performance), 1)

    @patch.object(MarketsRecorder, "get_instance")
    def test_store_all_positions(self, markets_recorder_mock):
        markets_recorder_mock.return_value = MagicMock(spec=MarketsRecorder)
        markets_recorder_mock.store_position = MagicMock(return_value=None)
        position_held = PositionHold("binance", "SOL-USDT", side=TradeType.BUY)
        executor_info = ExecutorInfo(
            id="123", timestamp=1234, type="position_executor",
            status=RunnableStatus.TERMINATED, config=PositionExecutorConfig(
                timestamp=1234, trading_pair="SOL-USDT", connector_name="binance",
                side=TradeType.BUY, amount=Decimal(10), entry_price=Decimal(100),
            ), net_pnl_pct=Decimal(0), net_pnl_quote=Decimal(0), cum_fees_quote=Decimal(0),
            filled_amount_quote=Decimal(100), is_active=False, is_trading=False,
            custom_info={"held_position_orders": [
                {"order_id": "123", "amount": Decimal(10), "trade_type": "BUY",
                 "executed_amount_base": Decimal("10"), "executed_amount_quote": Decimal("2300"),
                 "cumulative_fee_paid_quote": Decimal(0)}]},
            controller_id="main"
        )
        position_held.add_orders_from_executor(executor_info)
        self.orchestrator.positions_held = {
            "main": [position_held]
        }
        self.orchestrator.store_all_positions()
        self.assertEqual(len(self.orchestrator.positions_held["main"]), 0)

    def test_get_positions_report(self):
        position_held = PositionHold("binance", "SOL-USDT", side=TradeType.BUY)
        executor_info = ExecutorInfo(
            id="123", timestamp=1234, type="position_executor",
            status=RunnableStatus.TERMINATED, config=PositionExecutorConfig(
                timestamp=1234, trading_pair="SOL-USDT", connector_name="binance",
                side=TradeType.BUY, amount=Decimal(10), entry_price=Decimal(100),
            ), net_pnl_pct=Decimal(0), net_pnl_quote=Decimal(0), cum_fees_quote=Decimal(0),
            filled_amount_quote=Decimal(100), is_active=False, is_trading=False,
            custom_info={"held_position_orders": [
                {"order_id": "123", "amount": Decimal(10), "trade_type": "SELL",
                 "executed_amount_base": Decimal("10"), "executed_amount_quote": Decimal("2300"),
                 "cumulative_fee_paid_quote": Decimal(0)}]},
            controller_id="main"
        )
        position_held.add_orders_from_executor(executor_info)
        self.orchestrator.positions_held = {
            "main": [position_held]
        }
        report = self.orchestrator.get_positions_report()
        self.assertEqual(len(report), 1)
        self.assertEqual(report["main"][0].amount, Decimal(10))

    @patch.object(MarketsRecorder, "get_instance")
    def test_store_all_executors(self, markets_recorder_mock):
        markets_recorder_mock.return_value = MagicMock(spec=MarketsRecorder)
        markets_recorder_mock.store_or_update_executor = MagicMock(return_value=None)
        position_executor = MagicMock(spec=PositionExecutor)
        position_executor.is_active = False
        config_mock = MagicMock(PositionExecutorConfig)
        config_mock.id = "test"
        config_mock.controller_id = "test"
        position_executor.config = config_mock
        self.orchestrator.active_executors["test"] = [position_executor]
        self.orchestrator.store_all_executors()
        self.assertEqual(self.orchestrator.active_executors, {})

    @patch.object(ExecutorOrchestrator, "store_all_positions")
    def test_stop(self, store_all_positions):
        store_all_positions.return_value = None
        position_executor = MagicMock(spec=PositionExecutor)
        position_executor.is_closed = False
        position_executor.early_stop = MagicMock(return_value=None)
        self.orchestrator.active_executors["test"] = [position_executor]
        self.orchestrator.stop()
        position_executor.early_stop.assert_called_once()

    def test_stop_executor(self):
        position_executor = MagicMock(spec=PositionExecutor)
        position_executor.is_closed = False
        position_executor.early_stop = MagicMock(return_value=None)
        position_executor.config = MagicMock(PositionExecutorConfig)
        position_executor.config.id = "123"
        self.orchestrator.active_executors["test"] = [position_executor]
        self.orchestrator.stop_executor(StopExecutorAction(executor_id="123", controller_id="test"))
