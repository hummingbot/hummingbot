import unittest
from decimal import Decimal
from unittest.mock import MagicMock, PropertyMock, patch

from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import TradeType
from hummingbot.smart_components.executors.arbitrage_executor.arbitrage_executor import ArbitrageExecutor
from hummingbot.smart_components.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig, ExchangePair
from hummingbot.smart_components.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.smart_components.executors.dca_executor.dca_executor import DCAExecutor
from hummingbot.smart_components.executors.executor_orchestrator import ExecutorOrchestrator
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.models.executor_actions import CreateExecutorAction, StoreExecutorAction
from hummingbot.smart_components.models.executors import CloseType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class TestExecutorOrchestrator(unittest.TestCase):

    def setUp(self):
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
        return strategy

    @patch.object(PositionExecutor, "start")
    @patch.object(DCAExecutor, "start")
    @patch.object(ArbitrageExecutor, "start")
    def test_execute_actions_create_executor(self, arbitrage_start_mock: MagicMock, dca_start_mock: MagicMock, position_start_mock: MagicMock):
        position_executor_config = PositionExecutorConfig(
            timestamp=1234, connector_name="binance",
            trading_pair="ETH-USDT", side=TradeType.BUY, entry_price=Decimal(100), amount=Decimal(10))
        arbitrage_executor_config = ArbitrageExecutorConfig(
            timestamp=1234, order_amount=Decimal(10), min_profitability=Decimal(0.01),
            buying_market=ExchangePair(connector_name="binance", trading_pair="ETH-USDT"),
            selling_market=ExchangePair(connector_name="coinbase", trading_pair="ETH-USDT"),
        )
        dca_executor_config = DCAExecutorConfig(
            timestamp=1234, connector_name="binance", trading_pair="ETH-USDT",
            side=TradeType.BUY, amounts_quote=[Decimal(10)], prices=[Decimal(100)],)
        actions = [
            CreateExecutorAction(executor_config=position_executor_config, controller_id="test"),
            CreateExecutorAction(executor_config=arbitrage_executor_config, controller_id="test"),
            CreateExecutorAction(executor_config=dca_executor_config, controller_id="test")
        ]
        self.orchestrator.execute_actions(actions)
        self.assertEqual(len(self.orchestrator.executors["test"]), 3)

    @patch.object(MarketsRecorder, "store_or_update_executor")
    def test_execute_actions_store_executor_active(self, store_or_update_executor_mock: MagicMock):
        position_executor = MagicMock(spec=PositionExecutor)
        position_executor.is_active = True
        config_mock = MagicMock(PositionExecutorConfig)
        config_mock.id = "test"
        config_mock.controller_id = "test"
        position_executor.config = config_mock
        self.orchestrator.executors["test"] = [position_executor]
        actions = [StoreExecutorAction(executor_id="test", controller_id="test")]
        self.orchestrator.execute_actions(actions)
        self.assertEqual(len(self.orchestrator.executors["test"]), 1)
        store_or_update_executor_mock.assert_not_called()

    @patch.object(MarketsRecorder, "get_instance")
    def test_execute_actions_store_executor_inactive(self, _: MagicMock):
        position_executor = MagicMock(spec=PositionExecutor)
        position_executor.is_active = False
        config_mock = MagicMock(PositionExecutorConfig)
        config_mock.id = "test"
        config_mock.controller_id = "test"
        position_executor.config = config_mock
        self.orchestrator.executors["test"] = [position_executor]
        actions = [StoreExecutorAction(executor_id="test", controller_id="test")]
        self.orchestrator.execute_actions(actions)
        self.assertEqual(len(self.orchestrator.executors["test"]), 0)

    @patch('hummingbot.connector.markets_recorder.MarketsRecorder.get_instance')
    def test_generate_performance_report(self, mock_get_instance):
        # Create a mock for MarketsRecorder and its get_executors_by_controller method
        mock_markets_recorder = MagicMock(spec=MarketsRecorder)
        mock_markets_recorder.get_executors_by_controller.return_value = []
        mock_get_instance.return_value = mock_markets_recorder
        position_executor_non_active = MagicMock(spec=PositionExecutor)
        position_executor_non_active.is_active = False
        position_executor_non_active.close_type = CloseType.TAKE_PROFIT
        position_executor_non_active.net_pnl_quote = Decimal(10)
        position_executor_non_active.filled_amount_quote = Decimal(10)
        config_mock = MagicMock(PositionExecutorConfig)
        config_mock.id = "test"
        config_mock.controller_id = "test"
        position_executor_non_active.config = config_mock
        position_executor_active = MagicMock(spec=PositionExecutor)
        position_executor_active.is_active = True
        position_executor_active.net_pnl_quote = Decimal(10)
        position_executor_active.filled_amount_quote = Decimal(10)
        self.orchestrator.executors["test"] = [position_executor_non_active, position_executor_active]
        report = self.orchestrator.generate_performance_report(controller_id="test")
        self.assertEqual(report.realized_pnl_quote, Decimal(10))
        self.assertEqual(report.unrealized_pnl_quote, Decimal(10))
