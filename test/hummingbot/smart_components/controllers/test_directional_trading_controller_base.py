import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.common import PositionMode, TradeType
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.smart_components.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.models.executor_actions import ExecutorAction


class TestDirectionalTradingControllerBase(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        # Mocking the DirectionalTradingControllerConfigBase
        self.mock_controller_config = DirectionalTradingControllerConfigBase(
            id="test",
            controller_name="directional_trading_test_controller",
            connector_name="binance_perpetual",
            trading_pair="ETH-USDT",
            executor_amount_quote=Decimal(100.0),
            max_executors_per_side=2,
            cooldown_time=60 * 5,
            leverage=20,
            position_mode=PositionMode.HEDGE,
        )

        # Mocking dependencies
        self.mock_market_data_provider = MagicMock(spec=MarketDataProvider)
        self.mock_actions_queue = AsyncMock(spec=asyncio.Queue)

        # Instantiating the DirectionalTradingControllerBase
        self.controller = DirectionalTradingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )

    @patch.object(DirectionalTradingControllerBase, "get_signal")
    async def test_update_processed_data(self, get_signal_mock: MagicMock):
        get_signal_mock.return_value = Decimal("1")
        await self.controller.update_processed_data()
        self.assertEqual(self.controller.processed_data["signal"], Decimal("1"))\


    @patch.object(DirectionalTradingControllerBase, "get_signal")
    @patch.object(DirectionalTradingControllerBase, "get_executor_config")
    async def test_determine_executor_actions(self, get_executor_config_mock: MagicMock, get_signal_mock: MagicMock):
        get_signal_mock.return_value = Decimal("1")
        get_executor_config_mock.return_value = PositionExecutorConfig(
            timestamp=1234, controller_id=self.controller.config.id, connector_name="binance_perpetual",
            trading_pair="ETH-USDT", side=TradeType.BUY, entry_price=Decimal(100), amount=Decimal(10))
        await self.controller.update_processed_data()
        actions = self.controller.determine_executor_actions()
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].controller_id, "test")
        self.assertIsInstance(actions[0], ExecutorAction)
