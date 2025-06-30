import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.common import MarketDict, OrderType, PositionMode, TradeType
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy_v2.controllers.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)
from hummingbot.strategy_v2.executors.data_types import PositionSummary
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TrailingStop
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class TestMarketMakingControllerBase(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        # Mocking the MarketMakingControllerConfigBase
        self.mock_controller_config = MarketMakingControllerConfigBase(
            id="test",
            controller_name="market_making_test_controller",
            connector_name="binance_perpetual",
            trading_pair="ETH-USDT",
            total_amount_quote=Decimal(100.0),
            buy_spreads=[0.01, 0.02],
            sell_spreads=[0.01, 0.02],
            buy_amounts_pct=[Decimal(50), Decimal(50)],
            sell_amounts_pct=[Decimal(50), Decimal(50)],
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

    def test_update_markets_new_connector(self):
        markets = MarketDict()
        updated_markets = self.mock_controller_config.update_markets(markets)

        self.assertIn("binance_perpetual", updated_markets)
        self.assertIn("ETH-USDT", updated_markets["binance_perpetual"])

    def test_update_markets_existing_connector(self):
        markets = MarketDict({"binance_perpetual": {"BTC-USDT"}})
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

    def test_get_required_base_amount(self):
        # Test that get_required_base_amount calculates correctly
        controller_config = MarketMakingControllerConfigBase(
            id="test",
            controller_name="market_making_test_controller",
            connector_name="binance",
            trading_pair="ETH-USDT",
            total_amount_quote=Decimal("1000"),
            buy_spreads=[0.01, 0.02],
            sell_spreads=[0.01, 0.02],
            buy_amounts_pct=[Decimal(50), Decimal(50)],
            sell_amounts_pct=[Decimal(60), Decimal(40)],
            executor_refresh_time=300,
            cooldown_time=15,
            leverage=1,
            position_mode=PositionMode.HEDGE,
        )

        reference_price = Decimal("100")
        required_base_amount = controller_config.get_required_base_amount(reference_price)

        self.assertEqual(required_base_amount, Decimal("5"))

    def test_check_position_rebalance_perpetual(self):
        # Test that perpetual markets skip position rebalancing
        self.mock_controller_config.connector_name = "binance_perpetual"
        controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )
        controller.processed_data = {"reference_price": Decimal("100")}

        result = controller.check_position_rebalance()
        self.assertIsNone(result)

    def test_check_position_rebalance_no_reference_price(self):
        # Test early return when reference price is not available
        self.mock_controller_config.connector_name = "binance"  # Spot market
        controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )
        controller.processed_data = {}  # No reference price

        result = controller.check_position_rebalance()
        self.assertIsNone(result)

    def test_check_position_rebalance_active_rebalance_exists(self):
        # Test that no new rebalance is created when one is already active
        self.mock_controller_config.connector_name = "binance"  # Spot market
        controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )
        controller.processed_data = {"reference_price": Decimal("100")}

        # Create a mock active rebalance executor
        mock_executor = MagicMock(spec=ExecutorInfo)
        mock_executor.is_active = True
        mock_executor.custom_info = {"level_id": "position_rebalance"}
        controller.executors_info = [mock_executor]

        result = controller.check_position_rebalance()
        self.assertIsNone(result)

    def test_check_position_rebalance_below_threshold(self):
        # Test that no rebalance happens when difference is below threshold
        self.mock_controller_config.connector_name = "binance"  # Spot market
        self.mock_controller_config.position_rebalance_threshold_pct = Decimal("0.05")  # 5% threshold
        controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )
        controller.processed_data = {"reference_price": Decimal("100")}
        controller.executors_info = []  # No active executors

        # Mock positions_held to have almost enough base asset
        mock_position = MagicMock(spec=PositionSummary)
        mock_position.connector_name = "binance"
        mock_position.trading_pair = "ETH-USDT"
        mock_position.side = TradeType.BUY
        mock_position.amount = Decimal("0.99")  # Just slightly below 1.0 required
        controller.positions_held = [mock_position]

        with patch('hummingbot.strategy_v2.controllers.market_making_controller_base.MarketMakingControllerConfigBase.get_required_base_amount', return_value=Decimal("1.0")):
            result = controller.check_position_rebalance()

        # 0.99 vs 1.0 = 0.01 difference, which is 1% (below 5% threshold)
        self.assertIsNone(result)

    def test_check_position_rebalance_buy_needed(self):
        # Test that buy order is created when base asset is insufficient
        self.mock_controller_config.connector_name = "binance"  # Spot market
        self.mock_controller_config.position_rebalance_threshold_pct = Decimal("0.05")  # 5% threshold
        controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )
        controller.processed_data = {"reference_price": Decimal("100")}
        controller.executors_info = []  # No active executors
        controller.positions_held = []  # No positions held

        with patch('hummingbot.strategy_v2.controllers.market_making_controller_base.MarketMakingControllerConfigBase.get_required_base_amount', return_value=Decimal("10.0")):
            with patch.object(self.mock_market_data_provider, 'time', return_value=1234567890):
                result = controller.check_position_rebalance()

        # Should create a buy order for 10.0 base asset
        self.assertIsInstance(result, CreateExecutorAction)
        self.assertEqual(result.controller_id, "test")
        self.assertIsInstance(result.executor_config, OrderExecutorConfig)
        self.assertEqual(result.executor_config.side, TradeType.BUY)
        self.assertEqual(result.executor_config.amount, Decimal("10.0"))
        self.assertEqual(result.executor_config.execution_strategy, ExecutionStrategy.MARKET)

    def test_check_position_rebalance_sell_needed(self):
        # Test that sell order is created when base asset is excessive
        self.mock_controller_config.connector_name = "binance"  # Spot market
        self.mock_controller_config.position_rebalance_threshold_pct = Decimal("0.05")  # 5% threshold
        controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )
        controller.processed_data = {"reference_price": Decimal("100")}
        controller.executors_info = []  # No active executors

        # Mock positions_held to have too much base asset
        mock_position = MagicMock(spec=PositionSummary)
        mock_position.connector_name = "binance"
        mock_position.trading_pair = "ETH-USDT"
        mock_position.side = TradeType.BUY
        mock_position.amount = Decimal("15.0")  # More than required
        controller.positions_held = [mock_position]

        with patch('hummingbot.strategy_v2.controllers.market_making_controller_base.MarketMakingControllerConfigBase.get_required_base_amount', return_value=Decimal("10.0")):
            with patch.object(self.mock_market_data_provider, 'time', return_value=1234567890):
                result = controller.check_position_rebalance()

        # Should create a sell order for 5.0 base asset (15.0 - 10.0)
        self.assertIsInstance(result, CreateExecutorAction)
        self.assertEqual(result.controller_id, "test")
        self.assertIsInstance(result.executor_config, OrderExecutorConfig)
        self.assertEqual(result.executor_config.side, TradeType.SELL)
        self.assertEqual(result.executor_config.amount, Decimal("5.0"))
        self.assertEqual(result.executor_config.execution_strategy, ExecutionStrategy.MARKET)

    def test_get_current_base_position_buy_side(self):
        # Test calculation of current base position for buy side
        controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )

        # Mock buy position
        mock_position = MagicMock(spec=PositionSummary)
        mock_position.connector_name = "binance_perpetual"
        mock_position.trading_pair = "ETH-USDT"
        mock_position.side = TradeType.BUY
        mock_position.amount = Decimal("5.0")
        controller.positions_held = [mock_position]

        result = controller.get_current_base_position()
        self.assertEqual(result, Decimal("5.0"))

    def test_get_current_base_position_sell_side(self):
        # Test calculation of current base position for sell side
        controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )

        # Mock sell position
        mock_position = MagicMock(spec=PositionSummary)
        mock_position.connector_name = "binance_perpetual"
        mock_position.trading_pair = "ETH-USDT"
        mock_position.side = TradeType.SELL
        mock_position.amount = Decimal("3.0")
        controller.positions_held = [mock_position]

        result = controller.get_current_base_position()
        self.assertEqual(result, Decimal("-3.0"))

    def test_get_current_base_position_mixed(self):
        # Test calculation with both buy and sell positions
        controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )

        # Mock multiple positions
        mock_buy_position = MagicMock(spec=PositionSummary)
        mock_buy_position.connector_name = "binance_perpetual"
        mock_buy_position.trading_pair = "ETH-USDT"
        mock_buy_position.side = TradeType.BUY
        mock_buy_position.amount = Decimal("10.0")

        mock_sell_position = MagicMock(spec=PositionSummary)
        mock_sell_position.connector_name = "binance_perpetual"
        mock_sell_position.trading_pair = "ETH-USDT"
        mock_sell_position.side = TradeType.SELL
        mock_sell_position.amount = Decimal("3.0")

        # Include a position for different trading pair that should be ignored
        mock_other_position = MagicMock(spec=PositionSummary)
        mock_other_position.connector_name = "binance_perpetual"
        mock_other_position.trading_pair = "BTC-USDT"
        mock_other_position.side = TradeType.BUY
        mock_other_position.amount = Decimal("1.0")

        controller.positions_held = [mock_buy_position, mock_sell_position, mock_other_position]

        result = controller.get_current_base_position()
        self.assertEqual(result, Decimal("7.0"))  # 10.0 - 3.0

    def test_get_current_base_position_no_positions(self):
        # Test with no positions
        controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )
        controller.positions_held = []

        result = controller.get_current_base_position()
        self.assertEqual(result, Decimal("0"))

    def test_create_position_rebalance_order(self):
        # Test creation of position rebalance order
        controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )
        controller.processed_data = {"reference_price": Decimal("150")}

        with patch.object(self.mock_market_data_provider, 'time', return_value=1234567890):
            result = controller.create_position_rebalance_order(TradeType.BUY, Decimal("2.5"))

        self.assertIsInstance(result, CreateExecutorAction)
        self.assertEqual(result.controller_id, "test")
        self.assertIsInstance(result.executor_config, OrderExecutorConfig)
        self.assertEqual(result.executor_config.timestamp, 1234567890)
        self.assertEqual(result.executor_config.connector_name, "binance_perpetual")
        self.assertEqual(result.executor_config.trading_pair, "ETH-USDT")
        self.assertEqual(result.executor_config.execution_strategy, ExecutionStrategy.MARKET)
        self.assertEqual(result.executor_config.side, TradeType.BUY)
        self.assertEqual(result.executor_config.amount, Decimal("2.5"))
        self.assertEqual(result.executor_config.price, Decimal("150"))  # Will be ignored for market orders
        self.assertEqual(result.executor_config.level_id, "position_rebalance")

    def test_create_actions_proposal_with_position_rebalance(self):
        # Test that position rebalance action is added to create actions
        self.mock_controller_config.connector_name = "binance"  # Spot market
        controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )
        controller.processed_data = {"reference_price": Decimal("100"), "spread_multiplier": Decimal("1")}
        controller.executors_info = []  # No active executors
        controller.positions_held = []  # No positions

        # Mock the methods
        mock_rebalance_action = CreateExecutorAction(
            controller_id="test",
            executor_config=OrderExecutorConfig(
                timestamp=1234,
                connector_name="binance",
                trading_pair="ETH-USDT",
                execution_strategy=ExecutionStrategy.MARKET,
                side=TradeType.BUY,
                amount=Decimal("1.0"),
                price=Decimal("100"),
                level_id="position_rebalance",
                controller_id="test"
            )
        )

        with patch.object(controller, 'check_position_rebalance', return_value=mock_rebalance_action):
            with patch.object(controller, 'get_levels_to_execute', return_value=[]):
                with patch.object(controller, 'get_price_and_amount', return_value=(Decimal("100"), Decimal("1"))):
                    with patch.object(controller, 'get_executor_config', return_value=None):
                        actions = controller.create_actions_proposal()

        # Should include the rebalance action
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0], mock_rebalance_action)

    def test_create_actions_proposal_no_position_rebalance(self):
        # Test normal case where no position rebalance is needed
        self.mock_controller_config.connector_name = "binance"  # Spot market
        controller = MarketMakingControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )
        controller.processed_data = {"reference_price": Decimal("100"), "spread_multiplier": Decimal("1")}
        controller.executors_info = []  # No active executors
        controller.positions_held = []  # No positions

        with patch.object(controller, 'check_position_rebalance', return_value=None):
            with patch.object(controller, 'get_levels_to_execute', return_value=[]):
                actions = controller.create_actions_proposal()

        # Should not include any rebalance actions
        self.assertEqual(len(actions), 0)
