import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from controllers.market_making.pmm_simple import PMMSimpleConfig, PMMSimpleController
from hummingbot.core.data_type.common import PositionMode, TradeType
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig


class TestPMMSimpleController(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        self.config = PMMSimpleConfig(
            id="test_pmm",
            controller_name="pmm_simple",
            connector_name="binance",
            trading_pair="BTC-USDT",
            total_amount_quote=Decimal("100"),
            buy_spreads=[0.01, 0.02],
            sell_spreads=[0.01, 0.02],
            buy_amounts_pct=[Decimal("50"), Decimal("50")],
            sell_amounts_pct=[Decimal("50"), Decimal("50")],
            executor_refresh_time=60,
            cooldown_time=15,
            leverage=1,
            position_mode=PositionMode.HEDGE,
            skip_rebalance=False,
            position_rebalance_threshold_pct=Decimal("0.05"),
        )
        self.mock_market_data_provider = MagicMock(spec=MarketDataProvider)
        self.mock_actions_queue = AsyncMock(spec=asyncio.Queue)
        self.controller = PMMSimpleController(
            config=self.config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue,
        )

    def test_get_executor_config_valid_price(self):
        self.mock_market_data_provider.time.return_value = 1000
        executor_config = self.controller.get_executor_config(
            level_id="buy_0",
            price=Decimal("50000"),
            amount=Decimal("0.001"),
        )
        self.assertIsNotNone(executor_config)
        self.assertIsInstance(executor_config, PositionExecutorConfig)
        self.assertEqual(executor_config.entry_price, Decimal("50000"))
        self.assertEqual(executor_config.amount, Decimal("0.001"))
        self.assertEqual(executor_config.side, TradeType.BUY)
        self.assertEqual(executor_config.level_id, "buy_0")

    def test_get_executor_config_decimal_nan_price_returns_none(self):
        with patch.object(self.controller.logger(), "warning") as mock_warning:
            executor_config = self.controller.get_executor_config(
                level_id="buy_0",
                price=Decimal("NaN"),
                amount=Decimal("0.001"),
            )
            self.assertIsNone(executor_config)
            mock_warning.assert_called_once()
            self.assertIn("Invalid price", mock_warning.call_args[0][0])

    def test_get_executor_config_float_nan_price_returns_none(self):
        with patch.object(self.controller.logger(), "warning") as mock_warning:
            executor_config = self.controller.get_executor_config(
                level_id="sell_0",
                price=float("nan"),
                amount=Decimal("0.001"),
            )
            self.assertIsNone(executor_config)
            mock_warning.assert_called_once()
            self.assertIn("Invalid price", mock_warning.call_args[0][0])

    def test_get_executor_config_infinite_price_returns_none(self):
        with patch.object(self.controller.logger(), "warning") as mock_warning:
            executor_config = self.controller.get_executor_config(
                level_id="buy_0",
                price=Decimal("Infinity"),
                amount=Decimal("0.001"),
            )
            self.assertIsNone(executor_config)
            mock_warning.assert_called_once()

        with patch.object(self.controller.logger(), "warning") as mock_warning:
            executor_config = self.controller.get_executor_config(
                level_id="sell_0",
                price=float("inf"),
                amount=Decimal("0.001"),
            )
            self.assertIsNone(executor_config)
            mock_warning.assert_called_once()

    def test_get_executor_config_non_positive_price_returns_none(self):
        with patch.object(self.controller.logger(), "warning") as mock_warning:
            self.assertIsNone(self.controller.get_executor_config("buy_0", Decimal("0"), Decimal("1")))
            mock_warning.assert_called_once()

        with patch.object(self.controller.logger(), "warning") as mock_warning:
            self.assertIsNone(self.controller.get_executor_config("buy_0", Decimal("-100"), Decimal("1")))
            mock_warning.assert_called_once()

    def test_get_executor_config_nan_amount_returns_none(self):
        with patch.object(self.controller.logger(), "warning") as mock_warning:
            executor_config = self.controller.get_executor_config(
                level_id="buy_0",
                price=Decimal("50000"),
                amount=Decimal("NaN"),
            )
            self.assertIsNone(executor_config)
            mock_warning.assert_called_once()
            self.assertIn("Invalid price", mock_warning.call_args[0][0])

    def test_create_actions_proposal_with_nan_reference_price_emits_no_orders(self):
        # When reference_price is NaN (e.g. market data provider initializing)
        self.controller.processed_data = {
            "reference_price": Decimal("NaN"),
            "spread_multiplier": Decimal("1"),
        }
        self.controller.executors_info = []
        self.controller.positions_held = []

        actions = self.controller.create_actions_proposal()

        # No actions should be proposed (neither limit nor market order)
        self.assertEqual([], actions)

    def test_check_position_rebalance_with_nan_reference_price_emits_no_market_order(self):
        # Issue #7823 root cause: spot position rebalance attempted when reference_price is NaN
        self.controller.processed_data = {"reference_price": Decimal("NaN")}
        self.controller.executors_info = []
        self.controller.positions_held = []

        with patch.object(self.controller.logger(), "warning") as mock_warning:
            rebalance_action = self.controller.check_position_rebalance()
            self.assertIsNone(rebalance_action)
            mock_warning.assert_called_once()
            self.assertIn("Skipping position rebalance: invalid reference_price=NaN", mock_warning.call_args[0][0])
