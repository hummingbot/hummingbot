from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction
from scripts.lp_amm_executor_example import LPAmmExecutorExample, LPAmmExecutorExampleConfig


class TestLPAmmExecutorExample(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        self.connector_name = "solana-mainnet-beta"
        self.connector = MockPaperExchange()
        self.config = LPAmmExecutorExampleConfig(
            connector_name=self.connector_name,
            lp_provider="meteora/amm",
            trading_pair="SOL-USDC",
            pool_address="pool123",
            base_amount=Decimal("1"),
            quote_amount=Decimal("100"),
        )
        with patch('asyncio.create_task', return_value=MagicMock()):
            with patch(
                'hummingbot.strategy.strategy_v2_base.StrategyV2Base.listen_to_executor_actions',
                return_value=AsyncMock(),
            ):
                with patch('hummingbot.strategy.strategy_v2_base.ExecutorOrchestrator') as MockExecutorOrchestrator:
                    with patch('hummingbot.strategy.strategy_v2_base.MarketDataProvider') as MockMarketDataProvider:
                        self.strategy = LPAmmExecutorExample({self.connector_name: self.connector}, self.config)
                        self.strategy.executor_orchestrator = MockExecutorOrchestrator.return_value
                        self.strategy.market_data_provider = MockMarketDataProvider.return_value
        self.strategy.executor_orchestrator.get_all_reports.return_value = {}
        self.strategy.market_data_provider.ready = True
        self.strategy.logger().setLevel(1)

    def test_on_tick_creates_executor_exactly_once_across_repeated_ticks(self):
        self.strategy.on_tick()
        self.strategy.on_tick()
        self.strategy.on_tick()

        self.assertEqual(self.strategy.executor_orchestrator.execute_action.call_count, 1)
        action = self.strategy.executor_orchestrator.execute_action.call_args[0][0]
        self.assertIsInstance(action, CreateExecutorAction)
        self.assertEqual(action.executor_config.type, "lp_amm_executor")
        self.assertEqual(action.executor_config.connector_name, self.connector_name)
        self.assertEqual(action.executor_config.trading_pair, "SOL-USDC")
        self.assertEqual(action.executor_config.pool_address, "pool123")
        self.assertEqual(action.executor_config.base_amount, Decimal("1"))
        self.assertEqual(action.executor_config.quote_amount, Decimal("100"))

    def test_on_tick_does_nothing_when_market_data_not_ready(self):
        self.strategy.market_data_provider.ready = False

        self.strategy.on_tick()

        self.strategy.executor_orchestrator.execute_action.assert_not_called()

    def test_format_status_shows_executor_state_with_no_controllers(self):
        self.strategy.ready_to_trade = True
        executor_info = MagicMock(
            id="lp-1",
            status=RunnableStatus.RUNNING,
            is_active=True,
            timestamp=1234567890.0,
            custom_info={
                "state": "ACTIVE",
                "pool_address": "pool123",
                "base_amount": 1.0,
                "quote_amount": 100.0,
                "fees_earned_quote": 2.5,
                "fee_apr_pct": 12.3,
            },
        )
        self.strategy.controller_reports = {"main": {"executors": [executor_info], "positions": [], "performance": None}}
        with patch.object(LPAmmExecutorExample, "get_balance_df", return_value=MagicMock(to_string=lambda index: "")):
            with patch.object(LPAmmExecutorExample, "get_market_trading_pair_tuples", return_value=[]):
                with patch.object(LPAmmExecutorExample, "active_orders_df", side_effect=ValueError):
                    status = self.strategy.format_status()

        self.assertIn("lp-1", status)
        self.assertIn("RUNNING", status)
        self.assertIn("ACTIVE", status)
        self.assertIn("pool123", status)

    def test_format_status_unchanged_when_no_executors_yet(self):
        self.strategy.ready_to_trade = True
        self.strategy.controller_reports = {}
        with patch.object(LPAmmExecutorExample, "get_balance_df", return_value=MagicMock(to_string=lambda index: "")):
            with patch.object(LPAmmExecutorExample, "get_market_trading_pair_tuples", return_value=[]):
                with patch.object(LPAmmExecutorExample, "active_orders_df", side_effect=ValueError):
                    status = self.strategy.format_status()

        self.assertNotIn("LPAmmExecutor:", status)
