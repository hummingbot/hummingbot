import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy_v2.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TrailingStop
from hummingbot.strategy_v2.models.executor_actions import ExecutorAction, StopExecutorAction


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

    @patch("hummingbot.strategy_v2.controllers.market_making_controller_base.MarketMakingControllerBase.get_executor_config", new_callable=MagicMock)
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

    def test_validate_order_type(self):
        for order_type_name in OrderType.__members__:
            self.assertEqual(
                MarketMakingControllerConfigBase.validate_order_type(order_type_name),
                OrderType[order_type_name]
            )

        with self.assertRaises(ValueError):
            MarketMakingControllerConfigBase.validate_order_type("invalid_order_type")

    def test_triple_barrier_config(self):
        triple_barrier_config = self.mock_controller_config.triple_barrier_config
        self.assertEqual(triple_barrier_config.stop_loss, self.mock_controller_config.stop_loss)
        self.assertEqual(triple_barrier_config.take_profit, self.mock_controller_config.take_profit)
        self.assertEqual(triple_barrier_config.time_limit, self.mock_controller_config.time_limit)
        self.assertEqual(triple_barrier_config.trailing_stop, self.mock_controller_config.trailing_stop)

    def test_validate_position_mode(self):
        for position_mode_name in PositionMode.__members__:
            self.assertEqual(
                MarketMakingControllerConfigBase.validate_position_mode(position_mode_name),
                PositionMode[position_mode_name]
            )

        with self.assertRaises(ValueError):
            MarketMakingControllerConfigBase.validate_position_mode("invalid_position_mode")

    def test_update_parameters(self):
        new_spreads = [0.03, 0.04]
        new_amounts_pct = [60, 40]
        self.mock_controller_config.update_parameters(TradeType.BUY, new_spreads, new_amounts_pct)
        self.assertEqual(self.mock_controller_config.buy_spreads, new_spreads)
        self.assertEqual(self.mock_controller_config.buy_amounts_pct, new_amounts_pct)

        # Test without new_amounts_pct
        new_spreads = [0.05, 0.06]
        self.mock_controller_config.update_parameters(TradeType.SELL, new_spreads)
        self.assertEqual(self.mock_controller_config.sell_spreads, new_spreads)
        self.assertEqual(self.mock_controller_config.sell_amounts_pct, [1, 1])

    def test_update_markets_new_connector(self):
        markets = {}
        updated_markets = self.mock_controller_config.update_markets(markets)

        self.assertIn("binance_perpetual", updated_markets)
        self.assertIn("ETH-USDT", updated_markets["binance_perpetual"])

    def test_update_markets_existing_connector(self):
        markets = {"binance_perpetual": {"BTC-USDT"}}
        updated_markets = self.mock_controller_config.update_markets(markets)

        self.assertIn("binance_perpetual", updated_markets)
        self.assertIn("ETH-USDT", updated_markets["binance_perpetual"])
        self.assertIn("BTC-USDT", updated_markets["binance_perpetual"])

    def test_validate_target(self):
        self.assertEqual(None, self.mock_controller_config.validate_target(""))
        self.assertEqual(Decimal("2.0"), self.mock_controller_config.validate_target("2.0"))

    def test_parse_trailing_stop(self):
        self.assertEqual(None, self.mock_controller_config.parse_trailing_stop(""))
        trailing_stop = TrailingStop(activation_price=Decimal("2"), trailing_delta=Decimal(0.5))
        self.assertEqual(trailing_stop, self.mock_controller_config.parse_trailing_stop(trailing_stop))
