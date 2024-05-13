import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy_v2.controllers.directional_trading_controller_base import (
    DirectionalTradingControllerBase,
    DirectionalTradingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TrailingStop
from hummingbot.strategy_v2.models.executor_actions import ExecutorAction


class TestDirectionalTradingControllerBase(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        # Mocking the DirectionalTradingControllerConfigBase
        self.mock_controller_config = DirectionalTradingControllerConfigBase(
            id="test",
            controller_name="directional_trading_test_controller",
            connector_name="binance_perpetual",
            trading_pair="ETH-USDT",
            total_amount_quote=Decimal(100.0),
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

    async def test_update_processed_data(self):
        await self.controller.update_processed_data()
        self.assertEqual(self.controller.processed_data["signal"], 0)

    @patch.object(DirectionalTradingControllerBase, "get_executor_config")
    async def test_determine_executor_actions(self, get_executor_config_mock: MagicMock):
        get_executor_config_mock.return_value = PositionExecutorConfig(
            timestamp=1234, controller_id=self.controller.config.id, connector_name="binance_perpetual",
            trading_pair="ETH-USDT", side=TradeType.BUY, entry_price=Decimal(100), amount=Decimal(10))
        await self.controller.update_processed_data()
        self.controller.market_data_provider.time = MagicMock(return_value=1000000)
        self.controller.processed_data["signal"] = 1
        actions = self.controller.determine_executor_actions()
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].controller_id, "test")
        self.assertIsInstance(actions[0], ExecutorAction)

    def test_get_executor_config(self):
        trade_type = TradeType.BUY
        price = Decimal("100")
        amount = Decimal("1")

        executor_config = self.controller.get_executor_config(trade_type, price, amount)

        self.assertIsInstance(executor_config, PositionExecutorConfig)
        self.assertEqual(executor_config.connector_name, self.mock_controller_config.connector_name)
        self.assertEqual(executor_config.trading_pair, self.mock_controller_config.trading_pair)
        self.assertEqual(executor_config.side, trade_type)
        self.assertEqual(executor_config.entry_price, price)
        self.assertEqual(executor_config.amount, amount)

    def test_validate_order_type(self):
        for order_type_name in OrderType.__members__:
            self.assertEqual(
                DirectionalTradingControllerConfigBase.validate_order_type(order_type_name),
                OrderType[order_type_name]
            )

        with self.assertRaises(ValueError):
            DirectionalTradingControllerConfigBase.validate_order_type("invalid_order_type")

    def test_triple_barrier_config(self):
        config = self.mock_controller_config.triple_barrier_config

        self.assertEqual(config.stop_loss, Decimal("0.03"))
        self.assertEqual(config.take_profit, Decimal("0.02"))
        self.assertEqual(config.time_limit, 2700)
        self.assertEqual(config.trailing_stop.activation_price, Decimal("0.015"))
        self.assertEqual(config.trailing_stop.trailing_delta, Decimal("0.003"))

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
