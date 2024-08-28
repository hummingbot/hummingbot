import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pandas as pd

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.core.clock import Clock
from hummingbot.core.clock_mode import ClockMode
from hummingbot.core.data_type.common import PositionMode, TradeType
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo, PerformanceReport


class TestStrategyV2Base(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        self.start: pd.Timestamp = pd.Timestamp("2021-01-01", tz="UTC")
        self.end: pd.Timestamp = pd.Timestamp("2021-01-01 01:00:00", tz="UTC")
        self.start_timestamp: float = self.start.timestamp()
        self.end_timestamp: float = self.end.timestamp()
        self.clock_tick_size = 1
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.connector: MockPaperExchange = MockPaperExchange(
            client_config_map=ClientConfigAdapter(ClientConfigMap())
        )
        self.connector_name: str = "mock_paper_exchange"
        self.trading_pair: str = "HBOT-USDT"
        self.strategy_config = StrategyV2ConfigBase(markets={self.connector_name: {self.trading_pair}},
                                                    candles_config=[])
        with patch('asyncio.create_task', return_value=AsyncMock()):
            # Initialize the strategy with mock components
            with patch("hummingbot.strategy.strategy_v2_base.StrategyV2Base.listen_to_executor_actions", return_value=AsyncMock()):
                with patch('hummingbot.strategy.strategy_v2_base.ExecutorOrchestrator') as MockExecutorOrchestrator:
                    with patch('hummingbot.strategy.strategy_v2_base.MarketDataProvider') as MockMarketDataProvider:
                        self.strategy = StrategyV2Base({self.connector_name: self.connector}, config=self.strategy_config)
                        # Set mocks to strategy attributes
                        self.strategy.executor_orchestrator = MockExecutorOrchestrator.return_value
                        self.strategy.market_data_provider = MockMarketDataProvider.return_value
                        self.strategy.controllers = {'controller_1': MagicMock(), 'controller_2': MagicMock()}
        self.strategy.logger().setLevel(1)

    async def test_start(self):
        self.assertFalse(self.strategy.ready_to_trade)
        self.strategy.start(Clock(ClockMode.BACKTEST), self.start_timestamp)
        self.strategy.tick(self.start_timestamp + 10)
        self.assertTrue(self.strategy.ready_to_trade)

    def test_init_markets(self):
        StrategyV2Base.init_markets(self.strategy_config)
        self.assertIn(self.connector_name, StrategyV2Base.markets)
        self.assertIn(self.trading_pair, StrategyV2Base.markets[self.connector_name])

    def test_store_actions_proposal(self):
        # Setup test executors with all required fields
        executor_1 = ExecutorInfo(
            id="1",
            controller_id="controller_1",
            type="position_executor",
            status=RunnableStatus.TERMINATED,
            timestamp=10,
            config=PositionExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT",
                                          connector_name="binance",
                                          side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1")),
            net_pnl_pct=Decimal(0),
            net_pnl_quote=Decimal(0),
            cum_fees_quote=Decimal(0),
            filled_amount_quote=Decimal(0),
            is_active=False,
            is_trading=False,
            custom_info={}
        )
        executor_2 = ExecutorInfo(
            id="2",
            controller_id="controller_2",
            type="position_executor",
            status=RunnableStatus.RUNNING,
            timestamp=20,
            config=PositionExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT",
                                          connector_name="binance",
                                          side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1")),
            net_pnl_pct=Decimal(0),
            net_pnl_quote=Decimal(0),
            cum_fees_quote=Decimal(0),
            filled_amount_quote=Decimal(0),
            is_active=True,
            is_trading=True,
            custom_info={}
        )
        self.strategy.executors_info = {"controller_1": [executor_1], "controller_2": [executor_2]}
        self.strategy.closed_executors_buffer = 0

        actions = self.strategy.store_actions_proposal()
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].executor_id, "1")

    def test_get_executors_by_controller(self):
        self.strategy.executors_info = {
            "controller_1": [MagicMock(), MagicMock()],
            "controller_2": [MagicMock()]
        }

        executors = self.strategy.get_executors_by_controller("controller_1")
        self.assertEqual(len(executors), 2)

    def test_get_all_executors(self):
        self.strategy.executors_info = {
            "controller_1": [MagicMock(), MagicMock()],
            "controller_2": [MagicMock()]
        }

        executors = self.strategy.get_all_executors()
        self.assertEqual(len(executors), 3)

    def test_set_leverage(self):
        mock_connector = MagicMock()
        self.strategy.connectors = {"mock": mock_connector}
        self.strategy.set_leverage("mock", "HBOT-USDT", 2)
        mock_connector.set_leverage.assert_called_with("HBOT-USDT", 2)

    def test_set_position_mode(self):
        mock_connector = MagicMock()
        self.strategy.connectors = {"mock": mock_connector}
        self.strategy.set_position_mode("mock", PositionMode.HEDGE)
        mock_connector.set_position_mode.assert_called_with(PositionMode.HEDGE)

    def test_filter_executors(self):
        executors = [MagicMock(status=RunnableStatus.RUNNING), MagicMock(status=RunnableStatus.TERMINATED)]
        filtered = StrategyV2Base.filter_executors(executors, lambda x: x.status == RunnableStatus.RUNNING)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].status, RunnableStatus.RUNNING)

    def test_is_perpetual(self):
        self.assertTrue(StrategyV2Base.is_perpetual("binance_perpetual"))
        self.assertFalse(StrategyV2Base.is_perpetual("binance"))

    @patch.object(StrategyV2Base, "create_actions_proposal", return_value=[])
    @patch.object(StrategyV2Base, "stop_actions_proposal", return_value=[])
    @patch.object(StrategyV2Base, "store_actions_proposal", return_value=[])
    @patch.object(StrategyV2Base, "update_controllers_configs")
    @patch.object(StrategyV2Base, "update_executors_info")
    @patch("hummingbot.data_feed.market_data_provider.MarketDataProvider.ready", new_callable=PropertyMock)
    @patch("hummingbot.strategy_v2.executors.executor_orchestrator.ExecutorOrchestrator.execute_action")
    async def test_on_tick(self, mock_execute_action, mock_ready, mock_update_executors_info,
                           mock_update_controllers_configs,
                           mock_store_actions_proposal, mock_stop_actions_proposal, mock_create_actions_proposal):
        mock_ready.return_value = True
        self.strategy.on_tick()

        # Assertions to ensure that methods are called
        mock_update_executors_info.assert_called_once()
        mock_update_controllers_configs.assert_called_once()

        # Verify that the respective action proposal methods are called
        mock_create_actions_proposal.assert_called_once()
        mock_stop_actions_proposal.assert_called_once()
        mock_store_actions_proposal.assert_called_once()

        # Since no actions are returned, execute_action should not be called
        mock_execute_action.assert_not_called()

    async def test_on_stop(self):
        await self.strategy.on_stop()

        # Check if stop methods are called on each component
        self.strategy.executor_orchestrator.stop.assert_called_once()
        self.strategy.market_data_provider.stop.assert_called_once()

        # Check if stop is called on each controller
        for controller in self.strategy.controllers.values():
            controller.stop.assert_called_once()

    def test_parse_markets_str_valid(self):
        test_input = "binance.JASMY-USDT,RLC-USDT:kucoin.BTC-USDT"
        expected_output = {
            "binance": {"JASMY-USDT", "RLC-USDT"},
            "kucoin": {"BTC-USDT"}
        }
        result = StrategyV2ConfigBase.parse_markets_str(test_input)
        self.assertEqual(result, expected_output)

    def test_parse_markets_str_invalid(self):
        test_input = "invalid format"
        with self.assertRaises(ValueError):
            StrategyV2ConfigBase.parse_markets_str(test_input)

    def test_parse_candles_config_str_valid(self):
        test_input = "binance.JASMY-USDT.1m.500:kucoin.BTC-USDT.5m.200"
        result = StrategyV2ConfigBase.parse_candles_config_str(test_input)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].connector, "binance")
        self.assertEqual(result[0].trading_pair, "JASMY-USDT")
        self.assertEqual(result[0].interval, "1m")
        self.assertEqual(result[0].max_records, 500)

    def test_parse_candles_config_str_invalid_format(self):
        test_input = "invalid.format"
        with self.assertRaises(ValueError):
            StrategyV2ConfigBase.parse_candles_config_str(test_input)

    def test_parse_candles_config_str_invalid_max_records(self):
        test_input = "binance.JASMY-USDT.1m.invalid"
        with self.assertRaises(ValueError):
            StrategyV2ConfigBase.parse_candles_config_str(test_input)

    def create_mock_executor_config(self):
        return MagicMock(
            timestamp=1234567890,
            trading_pair="ETH-USDT",
            connector_name="binance",
            side="BUY",
            entry_price=Decimal("100"),
            amount=Decimal("1"),
            other_required_field=MagicMock()  # Add other fields as required by specific executor config
        )

    def test_executors_info_to_df(self):
        executor_1 = ExecutorInfo(
            id="1",
            controller_id="controller_1",
            type="position_executor",
            status=RunnableStatus.TERMINATED,
            timestamp=10,
            config=PositionExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT",
                                          connector_name="binance",
                                          side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1")),
            net_pnl_pct=Decimal(0),
            net_pnl_quote=Decimal(0),
            cum_fees_quote=Decimal(0),
            filled_amount_quote=Decimal(0),
            is_active=False,
            is_trading=False,
            custom_info={}
        )
        executor_2 = ExecutorInfo(
            id="2",
            controller_id="controller_2",
            type="position_executor",
            status=RunnableStatus.RUNNING,
            timestamp=20,
            config=PositionExecutorConfig(id="test", timestamp=1234567890, trading_pair="ETH-USDT",
                                          connector_name="binance",
                                          side=TradeType.BUY, entry_price=Decimal("100"), amount=Decimal("1")),
            net_pnl_pct=Decimal(0),
            net_pnl_quote=Decimal(0),
            cum_fees_quote=Decimal(0),
            filled_amount_quote=Decimal(0),
            is_active=True,
            is_trading=True,
            custom_info={}
        )

        executors_info = [executor_1, executor_2]
        df = StrategyV2Base.executors_info_to_df(executors_info)

        # Assertions to validate the DataFrame structure and content
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2)
        self.assertEqual(list(df.columns),
                         ['id',
                          'timestamp',
                          'type',
                          'close_timestamp',
                          'close_type',
                          'status',
                          'config',
                          'net_pnl_pct',
                          'net_pnl_quote',
                          'cum_fees_quote',
                          'filled_amount_quote',
                          'is_active',
                          'is_trading',
                          'custom_info',
                          'controller_id',
                          'side'])
        self.assertEqual(df.iloc[0]['id'], '2')  # Since the dataframe is sorted by status
        self.assertEqual(df.iloc[1]['id'], '1')
        self.assertEqual(df.iloc[0]['status'], RunnableStatus.RUNNING)
        self.assertEqual(df.iloc[1]['status'], RunnableStatus.TERMINATED)

    def create_mock_performance_report(self):
        return PerformanceReport(
            realized_pnl_quote=Decimal('100'),
            unrealized_pnl_quote=Decimal('50'),
            unrealized_pnl_pct=Decimal('5'),
            realized_pnl_pct=Decimal('10'),
            global_pnl_quote=Decimal('150'),
            global_pnl_pct=Decimal('15'),
            volume_traded=Decimal('1000'),
            open_order_volume=Decimal('0'),
            inventory_imbalance=Decimal('100'),
            close_type_counts={CloseType.TAKE_PROFIT: 10, CloseType.STOP_LOSS: 5}
        )

    @patch("hummingbot.strategy.strategy_v2_base.ScriptStrategyBase.format_status")
    def test_format_status(self, mock_super_format_status):
        # Mock dependencies
        original_status = "Super class status"
        mock_super_format_status.return_value = original_status

        controller_mock = MagicMock()
        controller_mock.to_format_status.return_value = ["Mock status for controller"]
        self.strategy.controllers = {"controller_1": controller_mock}

        mock_report_controller_1 = MagicMock()
        mock_report_controller_1.realized_pnl_quote = Decimal("100.00")
        mock_report_controller_1.unrealized_pnl_quote = Decimal("50.00")
        mock_report_controller_1.global_pnl_quote = Decimal("150.00")
        mock_report_controller_1.global_pnl_pct = Decimal("15.00")
        mock_report_controller_1.volume_traded = Decimal("1000.00")
        mock_report_controller_1.close_type_counts = {CloseType.TAKE_PROFIT: 10, CloseType.STOP_LOSS: 5}

        # Mocking generate_performance_report for main controller
        mock_report_main = MagicMock()
        mock_report_main.realized_pnl_quote = Decimal("200.00")
        mock_report_main.unrealized_pnl_quote = Decimal("75.00")
        mock_report_main.global_pnl_quote = Decimal("275.00")
        mock_report_main.global_pnl_pct = Decimal("15.00")
        mock_report_main.volume_traded = Decimal("2000.00")
        mock_report_main.close_type_counts = {CloseType.TAKE_PROFIT: 2, CloseType.STOP_LOSS: 3}
        self.strategy.executor_orchestrator.generate_performance_report = MagicMock(side_effect=[mock_report_controller_1, mock_report_main])
        # Mocking get_executors_by_controller for main controller to return an empty list
        self.strategy.get_executors_by_controller = MagicMock(return_value=[ExecutorInfo(
            id="12312", timestamp=1234567890, status=RunnableStatus.TERMINATED,
            config=self.get_position_config_market_short(), net_pnl_pct=Decimal(0), net_pnl_quote=Decimal(0),
            cum_fees_quote=Decimal(0), filled_amount_quote=Decimal(0), is_active=False, is_trading=False,
            custom_info={}, type="position_executor", controller_id="main")])

        # Call format_status
        status = self.strategy.format_status()

        # Assertions
        self.assertIn(original_status, status)
        self.assertIn("Mock status for controller", status)
        self.assertIn("Controller: controller_1", status)
        self.assertIn("Realized PNL (Quote): 100.00", status)
        self.assertIn("Unrealized PNL (Quote): 50.00", status)
        self.assertIn("Global PNL (Quote): 150", status)

    async def test_listen_to_executor_actions(self):
        self.strategy.actions_queue = MagicMock()
        # Simulate some actions being returned, followed by an exception to break the loop.
        self.strategy.actions_queue.get = AsyncMock(side_effect=[
            [CreateExecutorAction(controller_id="controller_1",
                                  executor_config=self.get_position_config_market_short())],
            Exception,
            asyncio.CancelledError,
        ])
        self.strategy.executor_orchestrator.execute_actions = AsyncMock()
        controller_mock = MagicMock()
        self.strategy.controllers = {"controller_1": controller_mock}

        # Test for exception handling inside the method.
        try:
            await self.strategy.listen_to_executor_actions()
        except asyncio.CancelledError:
            pass

        # Check assertions here to verify the actions were handled as expected.
        self.assertEqual(self.strategy.executor_orchestrator.execute_actions.call_count, 1)

    def get_position_config_market_short(self):
        return PositionExecutorConfig(id="test-2", timestamp=1234567890, trading_pair="ETH-USDT",
                                      connector_name="binance",
                                      side=TradeType.SELL, entry_price=Decimal("100"), amount=Decimal("1"),
                                      triple_barrier_config=TripleBarrierConfig())
