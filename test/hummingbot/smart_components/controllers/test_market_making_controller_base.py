import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.common import PositionMode, TradeType
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.smart_components.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.models.executor_actions import ExecutorAction, StopExecutorAction, StoreExecutorAction


class TestMarketMakingControllerBase(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        # Mocking the MarketMakingControllerConfigBase
        self.mock_controller_config = MarketMakingControllerConfigBase(
            id="test",
            controller_name="market_making_test_controller",
            connector_name="binance_perpetual",
            trading_pair="ETH-USDT",
            total_amount_quote=100.0,
            buy_spreads=[0.01, 0.02],
            sell_spreads=[0.01, 0.02],
            buy_amounts_pct=[50, 50],
            sell_amounts_pct=[50, 50],
            executor_refresh_time=300,
            cooldown_time=15,
            leverage=20,
            position_mode=PositionMode.HEDGE,
        )

        # Mocking dependencies
        self.mock_market_data_provider = MagicMock(spec=MarketDataProvider)
        self.mock_actions_queue = AsyncMock(spec=asyncio.Queue)

        # Instantiating the MarketMakingControllerBase
        self.controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )

    async def test_update_processed_data(self):
        type(self.mock_market_data_provider).get_price_by_type = MagicMock(return_value=Decimal("100"))
        await self.controller.update_processed_data()
        self.assertEqual(self.controller.processed_data["reference_price"], Decimal("100"))
        self.assertEqual(self.controller.processed_data["spread_multiplier"], Decimal("1"))

    @patch("hummingbot.smart_components.controllers.market_making_controller_base.MarketMakingControllerBase.get_executor_config", new_callable=MagicMock)
    async def test_determine_executor_actions(self, executor_config_mock: MagicMock):
        executor_config_mock.return_value = PositionExecutorConfig(
            timestamp=1234, controller_id=self.controller.config.id, connector_name="binance_perpetual",
            trading_pair="ETH-USDT", side=TradeType.BUY, entry_price=Decimal(100), amount=Decimal(10))
        type(self.mock_market_data_provider).get_price_by_type = MagicMock(return_value=Decimal("100"))
        await self.controller.update_processed_data()
        actions = self.controller.determine_executor_actions()
        self.assertIsInstance(actions, list)
        for action in actions:
            self.assertIsInstance(action, ExecutorAction)

    def test_stop_actions_proposal(self):
        stop_actions = self.controller.stop_actions_proposal()
        self.assertIsInstance(stop_actions, list)
        for action in stop_actions:
            self.assertIsInstance(action, StopExecutorAction)

    def test_store_actions_proposal(self):
        store_actions = self.controller.store_actions_proposal()
        self.assertIsInstance(store_actions, list)
        for action in store_actions:
            self.assertIsInstance(action, StoreExecutorAction)
