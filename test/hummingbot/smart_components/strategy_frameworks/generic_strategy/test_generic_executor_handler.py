from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.smart_components.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig, ExchangePair
from hummingbot.smart_components.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.models.executor_actions import (
    CreateExecutorAction,
    StopExecutorAction,
    StoreExecutorAction,
)
from hummingbot.smart_components.strategy_frameworks.controller_base import ControllerConfigBase
from hummingbot.smart_components.strategy_frameworks.generic_strategy.generic_controller import GenericController
from hummingbot.smart_components.strategy_frameworks.generic_strategy.generic_executor import GenericExecutor


class TestGenericExecutor(IsolatedAsyncioWrapperTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.strategy = MagicMock()
        self.controller = GenericController(config=ControllerConfigBase(
            id="test-controller",
            exchange="test-exchange",
            trading_pair="test-trading-pair",
            strategy_name="test-strategy",
            candles_config=[],
        ))
        type(self.controller).is_perpetual = MagicMock(return_value=True)
        self.generic_executor = GenericExecutor(self.strategy, self.controller)

    @patch.object(GenericExecutor, "set_leverage_and_position_mode")
    async def test_on_start(self, mock_set_leverage_and_position_mode):
        self.generic_executor.on_start()
        mock_set_leverage_and_position_mode.assert_called()

    async def test_stop(self):
        self.generic_executor.stop()
        self.assertEqual(self.generic_executor.position_executors, [])

    async def test_control_task_create_executor_action(self):
        self.generic_executor.get_executor_handler_report = MagicMock()
        self.generic_executor.controller.update_executor_handler_report = AsyncMock()
        self.generic_executor.controller.determine_actions = AsyncMock(return_value=[
            CreateExecutorAction(
                controller_id="test-controller",
                executor_config=PositionExecutorConfig(
                    id="test-1", timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                    open_order_type=OrderType.LIMIT, side=TradeType.BUY, entry_price=Decimal("100"),
                    amount=Decimal("1"), stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60)),
            CreateExecutorAction(
                controller_id="test-controller",
                executor_config=DCAExecutorConfig(
                    id="test-2", timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                    side=TradeType.BUY, amounts_quote=[Decimal("1"), Decimal("2")],
                    prices=[Decimal("100"), Decimal("90")], time_limit=60)),
            CreateExecutorAction(
                controller_id="test-controller",
                executor_config=ArbitrageExecutorConfig(
                    id="test-3", timestamp=1234567890, min_profitability=Decimal("0.01"), order_amount=Decimal("1"),
                    buying_market=ExchangePair(exchange="binance", trading_pair="ETH-USDT"),
                    selling_market=ExchangePair(exchange="kucoin", trading_pair="ETH-USDT"),
                )
            )
        ])
        await self.generic_executor.control_task()
        self.generic_executor.get_executor_handler_report.assert_called()
        self.generic_executor.controller.update_executor_handler_report.assert_called()
        self.generic_executor.controller.determine_actions.assert_called()
        self.assertEqual(len(self.generic_executor.position_executors), 1)
        self.assertEqual(len(self.generic_executor.dca_executors), 1)
        self.assertEqual(len(self.generic_executor.arbitrage_executors), 1)

    async def test_control_task_no_action(self):
        self.generic_executor.get_executor_handler_report = MagicMock()
        self.generic_executor.controller.update_executor_handler_report = AsyncMock()
        self.generic_executor.controller.determine_actions = AsyncMock(return_value=[])
        await self.generic_executor.control_task()
        self.generic_executor.get_executor_handler_report.assert_called()
        self.generic_executor.controller.update_executor_handler_report.assert_called()
        self.generic_executor.controller.determine_actions.assert_called()
        self.assertEqual(self.generic_executor.position_executors, [])
        self.assertEqual(self.generic_executor.dca_executors, [])
        self.assertEqual(self.generic_executor.arbitrage_executors, [])

    async def test_control_task_stop_executor_action(self):
        self.generic_executor.get_executor_handler_report = MagicMock()
        self.generic_executor.controller.update_executor_handler_report = AsyncMock()
        position_executor = MagicMock()
        position_executor.is_active = True
        position_executor.config = MagicMock()
        position_executor.config.id = "test-1"
        self.generic_executor.position_executors = [position_executor]
        self.generic_executor.controller.determine_actions = AsyncMock(return_value=[StopExecutorAction(
            controller_id="test-controller",
            executor_id="test-1")])
        await self.generic_executor.control_task()
        self.generic_executor.get_executor_handler_report.assert_called()
        self.generic_executor.controller.update_executor_handler_report.assert_called()
        self.generic_executor.controller.determine_actions.assert_called()
        position_executor.early_stop.assert_called()

    @patch.object(MarketsRecorder, "get_instance")
    async def test_control_task_store_executor_action(self, markets_recorder_mock):
        self.generic_executor.get_executor_handler_report = MagicMock()
        self.generic_executor.controller.update_executor_handler_report = AsyncMock()
        self.generic_executor.controller.determine_actions = AsyncMock(return_value=[
            CreateExecutorAction(
                controller_id="test-controller",
                executor_config=DCAExecutorConfig(
                    id="test-1", timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                    side=TradeType.BUY, amounts_quote=[Decimal("1"), Decimal("2")],
                    prices=[Decimal("100"), Decimal("90")], time_limit=60)),])
        await self.generic_executor.control_task()
        self.generic_executor.dca_executors[0]._status = SmartComponentStatus.TERMINATED
        self.generic_executor.controller.determine_actions = AsyncMock(return_value=[StoreExecutorAction(
            controller_id="test-controller",
            executor_id="test-1")])
        await self.generic_executor.control_task()
        self.generic_executor.get_executor_handler_report.assert_called()
        self.generic_executor.controller.update_executor_handler_report.assert_called()
        self.generic_executor.controller.determine_actions.assert_called()
        self.assertEqual(self.generic_executor.position_executors, [])
        self.assertEqual(self.generic_executor.dca_executors, [])

    async def test_control_task_unknown_action(self):
        self.generic_executor.get_executor_handler_report = MagicMock()
        self.generic_executor.controller.update_executor_handler_report = AsyncMock()
        self.generic_executor.controller.determine_actions = AsyncMock(return_value=["unknown-action"])
        with self.assertRaises(ValueError):
            await self.generic_executor.control_task()
