from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock, patch

from hummingbot.core.data_type.common import TradeType
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorStatus, TripleBarrierConf
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevel
from hummingbot.smart_components.strategy_frameworks.directional_trading import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
    DirectionalTradingExecutorHandler,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class TestDirectionalTradingExecutorHandler(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        # Mocking the necessary components
        self.mock_strategy = MagicMock(spec=ScriptStrategyBase)
        self.mock_controller = MagicMock(spec=DirectionalTradingControllerBase)
        triple_barrier_conf = TripleBarrierConf(
            stop_loss=Decimal("0.03"), take_profit=Decimal("0.02"),
            time_limit=60 * 60 * 24,
            trailing_stop_activation_price=Decimal("0.002"),
            trailing_stop_trailing_delta=Decimal("0.0005")
        )
        self.mock_controller.config = MagicMock(spec=DirectionalTradingControllerConfigBase)
        self.mock_controller.config.exchange = "binance"
        self.mock_controller.config.trading_pair = "BTC-USDT"
        self.mock_controller.config.order_levels = [
            OrderLevel(level=1, side=TradeType.BUY, order_amount_usd=Decimal("100"),
                       spread_factor=Decimal("0.01"), triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=1, side=TradeType.SELL, order_amount_usd=Decimal("100"),
                       spread_factor=Decimal("0.01"), triple_barrier_conf=triple_barrier_conf)
        ]

        # Instantiating the DirectionalTradingExecutorHandler
        self.handler = DirectionalTradingExecutorHandler(
            strategy=self.mock_strategy,
            controller=self.mock_controller
        )

    @patch(
        "hummingbot.smart_components.strategy_frameworks.executor_handler_base.ExecutorHandlerBase.close_open_positions")
    def test_on_stop_perpetual(self, mock_close_open_positions):
        self.mock_controller.is_perpetual = True
        self.handler.on_stop()
        mock_close_open_positions.assert_called_once()

    @patch(
        "hummingbot.smart_components.strategy_frameworks.executor_handler_base.ExecutorHandlerBase.close_open_positions")
    def test_on_stop_non_perpetual(self, mock_close_open_positions):
        self.mock_controller.is_perpetual = False
        self.handler.on_stop()
        mock_close_open_positions.assert_not_called()

    @patch(
        "hummingbot.smart_components.strategy_frameworks.directional_trading.directional_trading_executor_handler.DirectionalTradingExecutorHandler.set_leverage_and_position_mode")
    def test_on_start_perpetual(self, mock_set_leverage):
        self.mock_controller.is_perpetual = True
        self.handler.on_start()
        mock_set_leverage.assert_called_once()

    @patch(
        "hummingbot.smart_components.strategy_frameworks.directional_trading.directional_trading_executor_handler.DirectionalTradingExecutorHandler.set_leverage_and_position_mode")
    def test_on_start_non_perpetual(self, mock_set_leverage):
        self.mock_controller.is_perpetual = False
        self.handler.on_start()
        mock_set_leverage.assert_not_called()

    @patch("hummingbot.smart_components.strategy_frameworks.executor_handler_base.ExecutorHandlerBase.create_position_executor")
    async def test_control_task_all_candles_ready(self, mock_create_executor):
        self.mock_controller.all_candles_ready = True
        await self.handler.control_task()
        mock_create_executor.assert_called()

    @patch("hummingbot.smart_components.strategy_frameworks.executor_handler_base.ExecutorHandlerBase.create_position_executor")
    async def test_control_task_candles_not_ready(self, mock_create_executor):
        self.mock_controller.all_candles_ready = False
        await self.handler.control_task()
        mock_create_executor.assert_not_called()

    @patch("hummingbot.smart_components.strategy_frameworks.executor_handler_base.ExecutorHandlerBase.store_position_executor")
    async def test_control_task_executor_closed_not_in_cooldown(self, mock_store_executor):
        self.mock_controller.all_candles_ready = True
        mock_executor = MagicMock()
        mock_executor.is_closed = True
        mock_executor.executor_status = PositionExecutorStatus.COMPLETED
        self.handler.position_executors["BUY_1"] = mock_executor
        self.handler.position_executors["SELL_1"] = mock_executor
        self.mock_controller.cooldown_condition.return_value = False
        await self.handler.control_task()
        mock_store_executor.assert_called()

    @patch("hummingbot.smart_components.strategy_frameworks.executor_handler_base.ExecutorHandlerBase.create_position_executor")
    async def test_control_task_no_executor(self, mock_create_executor):
        self.mock_controller.all_candles_ready = True
        await self.handler.control_task()
        mock_create_executor.assert_called()
