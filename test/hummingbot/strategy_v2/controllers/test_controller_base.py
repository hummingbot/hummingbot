import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from hummingbot.core.data_type.common import PriceType, TradeType
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase, ExecutorFilter
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, LimitChaserConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class TestControllerBase(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        # Mocking the ControllerConfigBase
        self.mock_controller_config = ControllerConfigBase(
            id="test",
            controller_name="test_controller",
            controller_type="generic"
        )

        # Mocking dependencies
        self.mock_market_data_provider = MagicMock(spec=MarketDataProvider)
        self.mock_actions_queue = AsyncMock(spec=asyncio.Queue)

        # Instantiating the ControllerBase
        self.controller = ControllerBase(
            config=self.mock_controller_config,
            market_data_provider=self.mock_market_data_provider,
            actions_queue=self.mock_actions_queue
        )

    def create_mock_executor_info(self, executor_id: str, connector_name: str = "binance",
                                  trading_pair: str = "BTC-USDT", executor_type: str = "PositionExecutor",
                                  is_active: bool = True, status: RunnableStatus = RunnableStatus.RUNNING,
                                  side: TradeType = TradeType.BUY, net_pnl_pct: Decimal = Decimal("0.01"),
                                  timestamp: float = 1640995200.0, controller_id: str = "test_controller"):
        """Helper method to create mock ExecutorInfo objects for testing"""
        mock_config = MagicMock()
        mock_config.trading_pair = trading_pair
        mock_config.connector_name = connector_name
        mock_config.amount = Decimal("1.0")

        mock_executor = MagicMock(spec=ExecutorInfo)
        mock_executor.id = executor_id
        mock_executor.type = executor_type
        mock_executor.status = status
        mock_executor.is_active = is_active
        mock_executor.is_trading = True
        mock_executor.config = mock_config
        mock_executor.trading_pair = trading_pair
        mock_executor.connector_name = connector_name
        mock_executor.side = side
        mock_executor.net_pnl_pct = net_pnl_pct
        mock_executor.net_pnl_quote = Decimal("10.0")
        mock_executor.filled_amount_quote = Decimal("100.0")
        mock_executor.timestamp = timestamp
        mock_executor.close_timestamp = None
        mock_executor.close_type = None
        mock_executor.controller_id = controller_id
        mock_executor.custom_info = {"order_ids": [f"order_{executor_id}"]}

        return mock_executor

    def test_initialize_candles(self):
        # Mock get_candles_config to return some config so initialize_candles_feed gets called
        from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
        mock_config = CandlesConfig(
            connector="binance",
            trading_pair="ETH-USDT",
            interval="1m",
            max_records=100
        )
        self.controller.get_candles_config = MagicMock(return_value=[mock_config])

        # Test whether candles are initialized correctly
        self.controller.initialize_candles()
        self.mock_market_data_provider.initialize_candles_feed.assert_called_once_with(mock_config)

    def test_update_config(self):
        # Test the update_config method
        from decimal import Decimal
        new_config = ControllerConfigBase(
            id="test_new",
            controller_name="new_test_controller",
            controller_type="market_making",
            total_amount_quote=Decimal("200"),
            manual_kill_switch=True
        )
        self.controller.update_config(new_config)
        # Controller name is not updatable
        self.assertEqual(self.controller.config.controller_name, "test_controller")

        # Total amount quote is updatable
        self.assertEqual(self.controller.config.total_amount_quote, Decimal("200"))

        # Manual kill switch is updatable
        self.assertEqual(self.controller.config.manual_kill_switch, True)

    async def test_control_task_market_data_provider_not_ready(self):
        type(self.controller.market_data_provider).ready = PropertyMock(return_value=False)
        self.controller.executors_update_event.set()
        self.controller.update_processed_data = AsyncMock()
        self.controller.determine_executor_actions = MagicMock(return_value=[])
        await self.controller.control_task()
        # Check that no action is put in the queue
        self.mock_actions_queue.put.assert_not_called()

    async def test_control_task_executors_update_event_not_set(self):
        type(self.controller.market_data_provider).ready = PropertyMock(return_value=False)
        self.controller.executors_update_event.clear()
        await self.controller.control_task()
        # Check that no action is put in the queue
        self.mock_actions_queue.put.assert_not_called()

    async def test_control_task(self):
        type(self.controller.market_data_provider).ready = PropertyMock(return_value=True)
        self.controller.executors_update_event.set()
        self.controller.update_processed_data = AsyncMock()
        self.controller.determine_executor_actions = MagicMock(return_value=[])
        await self.controller.control_task()
        # Check that no action is put in the queue
        self.mock_actions_queue.put.assert_not_called()

    def test_to_format_status(self):
        # Test the to_format_status method
        status = self.controller.to_format_status()
        self.assertIsInstance(status, list)

    def test_get_custom_info(self):
        # Test the get_custom_info method returns empty dict by default
        custom_info = self.controller.get_custom_info()
        self.assertIsInstance(custom_info, dict)
        self.assertEqual(custom_info, {})

    # Tests for ExecutorFilter functionality

    def test_executor_filter_creation(self):
        """Test ExecutorFilter can be created with all parameters"""
        executor_filter = ExecutorFilter(
            executor_ids=["exec1", "exec2"],
            connector_names=["binance", "coinbase"],
            trading_pairs=["BTC-USDT", "ETH-USDT"],
            executor_types=["PositionExecutor", "DCAExecutor"],
            statuses=[RunnableStatus.RUNNING, RunnableStatus.TERMINATED],
            sides=[TradeType.BUY, TradeType.SELL],
            is_active=True,
            is_trading=False,
            close_types=[CloseType.COMPLETED],
            controller_ids=["controller1"],
            min_pnl_pct=Decimal("-0.05"),
            max_pnl_pct=Decimal("0.10"),
            min_timestamp=1640995200.0,
            max_timestamp=1672531200.0
        )

        self.assertEqual(executor_filter.executor_ids, ["exec1", "exec2"])
        self.assertEqual(executor_filter.connector_names, ["binance", "coinbase"])
        self.assertEqual(executor_filter.trading_pairs, ["BTC-USDT", "ETH-USDT"])
        self.assertEqual(executor_filter.executor_types, ["PositionExecutor", "DCAExecutor"])
        self.assertEqual(executor_filter.statuses, [RunnableStatus.RUNNING, RunnableStatus.TERMINATED])
        self.assertEqual(executor_filter.sides, [TradeType.BUY, TradeType.SELL])
        self.assertTrue(executor_filter.is_active)
        self.assertFalse(executor_filter.is_trading)
        self.assertEqual(executor_filter.min_pnl_pct, Decimal("-0.05"))
        self.assertEqual(executor_filter.max_pnl_pct, Decimal("0.10"))

    def test_filter_executors_by_connector_names(self):
        """Test filtering executors by connector names"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", connector_name="binance"),
            self.create_mock_executor_info("exec2", connector_name="coinbase"),
            self.create_mock_executor_info("exec3", connector_name="kraken")
        ]

        # Test filtering by single connector
        executor_filter = ExecutorFilter(connector_names=["binance"])
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].id, "exec1")

        # Test filtering by multiple connectors
        executor_filter = ExecutorFilter(connector_names=["binance", "coinbase"])
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 2)
        self.assertIn("exec1", [e.id for e in filtered])
        self.assertIn("exec2", [e.id for e in filtered])

    def test_filter_executors_by_trading_pairs(self):
        """Test filtering executors by trading pairs"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", trading_pair="BTC-USDT"),
            self.create_mock_executor_info("exec2", trading_pair="ETH-USDT"),
            self.create_mock_executor_info("exec3", trading_pair="ADA-USDT")
        ]

        # Test filtering by single trading pair
        executor_filter = ExecutorFilter(trading_pairs=["BTC-USDT"])
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].id, "exec1")

        # Test filtering by multiple trading pairs
        executor_filter = ExecutorFilter(trading_pairs=["BTC-USDT", "ETH-USDT"])
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 2)
        self.assertIn("exec1", [e.id for e in filtered])
        self.assertIn("exec2", [e.id for e in filtered])

    def test_filter_executors_by_executor_types(self):
        """Test filtering executors by executor types"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", executor_type="PositionExecutor"),
            self.create_mock_executor_info("exec2", executor_type="DCAExecutor"),
            self.create_mock_executor_info("exec3", executor_type="GridExecutor")
        ]

        # Test filtering by single executor type
        executor_filter = ExecutorFilter(executor_types=["PositionExecutor"])
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].id, "exec1")

        # Test filtering by multiple executor types
        executor_filter = ExecutorFilter(executor_types=["PositionExecutor", "DCAExecutor"])
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 2)
        self.assertIn("exec1", [e.id for e in filtered])
        self.assertIn("exec2", [e.id for e in filtered])

    def test_filter_executors_by_sides(self):
        """Test filtering executors by trading sides"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", side=TradeType.BUY),
            self.create_mock_executor_info("exec2", side=TradeType.SELL),
            self.create_mock_executor_info("exec3", side=TradeType.BUY)
        ]

        # Test filtering by BUY side
        executor_filter = ExecutorFilter(sides=[TradeType.BUY])
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 2)
        self.assertIn("exec1", [e.id for e in filtered])
        self.assertIn("exec3", [e.id for e in filtered])

        # Test filtering by SELL side
        executor_filter = ExecutorFilter(sides=[TradeType.SELL])
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].id, "exec2")

    def test_filter_executors_by_active_status(self):
        """Test filtering executors by active status"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", is_active=True),
            self.create_mock_executor_info("exec2", is_active=False),
            self.create_mock_executor_info("exec3", is_active=True)
        ]

        # Test filtering by active status
        executor_filter = ExecutorFilter(is_active=True)
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 2)
        self.assertIn("exec1", [e.id for e in filtered])
        self.assertIn("exec3", [e.id for e in filtered])

        # Test filtering by inactive status
        executor_filter = ExecutorFilter(is_active=False)
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].id, "exec2")

    def test_filter_executors_by_pnl_range(self):
        """Test filtering executors by PnL ranges"""
        # Setup mock executors with different PnL values
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", net_pnl_pct=Decimal("-0.10")),  # -10%
            self.create_mock_executor_info("exec2", net_pnl_pct=Decimal("0.05")),   # +5%
            self.create_mock_executor_info("exec3", net_pnl_pct=Decimal("0.15"))    # +15%
        ]

        # Test filtering by min PnL
        executor_filter = ExecutorFilter(min_pnl_pct=Decimal("0.00"))
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 2)  # Only positive PnL executors
        self.assertIn("exec2", [e.id for e in filtered])
        self.assertIn("exec3", [e.id for e in filtered])

        # Test filtering by max PnL
        executor_filter = ExecutorFilter(max_pnl_pct=Decimal("0.10"))
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 2)  # PnL <= 10%
        self.assertIn("exec1", [e.id for e in filtered])
        self.assertIn("exec2", [e.id for e in filtered])

        # Test filtering by PnL range
        executor_filter = ExecutorFilter(min_pnl_pct=Decimal("0.00"), max_pnl_pct=Decimal("0.10"))
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 1)  # Only exec2 in 0-10% range
        self.assertEqual(filtered[0].id, "exec2")

    def test_filter_executors_by_timestamp_range(self):
        """Test filtering executors by timestamp ranges"""
        # Setup mock executors with different timestamps
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", timestamp=1640995200.0),  # Jan 1, 2022
            self.create_mock_executor_info("exec2", timestamp=1656633600.0),  # Jul 1, 2022
            self.create_mock_executor_info("exec3", timestamp=1672531200.0)   # Jan 1, 2023
        ]

        # Test filtering by min timestamp
        executor_filter = ExecutorFilter(min_timestamp=1656633600.0)
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 2)  # exec2 and exec3
        self.assertIn("exec2", [e.id for e in filtered])
        self.assertIn("exec3", [e.id for e in filtered])

        # Test filtering by max timestamp
        executor_filter = ExecutorFilter(max_timestamp=1656633600.0)
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 2)  # exec1 and exec2
        self.assertIn("exec1", [e.id for e in filtered])
        self.assertIn("exec2", [e.id for e in filtered])

    def test_filter_executors_combined_criteria(self):
        """Test filtering executors with multiple criteria combined"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", connector_name="binance", side=TradeType.BUY, is_active=True),
            self.create_mock_executor_info("exec2", connector_name="binance", side=TradeType.SELL, is_active=True),
            self.create_mock_executor_info("exec3", connector_name="coinbase", side=TradeType.BUY, is_active=True),
            self.create_mock_executor_info("exec4", connector_name="binance", side=TradeType.BUY, is_active=False)
        ]

        # Test combined filtering: binance + BUY + active
        executor_filter = ExecutorFilter(
            connector_names=["binance"],
            sides=[TradeType.BUY],
            is_active=True
        )
        filtered = self.controller.filter_executors(executor_filter=executor_filter)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].id, "exec1")

    def test_get_active_executors(self):
        """Test get_active_executors convenience method"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", connector_name="binance", is_active=True),
            self.create_mock_executor_info("exec2", connector_name="coinbase", is_active=False),
            self.create_mock_executor_info("exec3", connector_name="binance", is_active=True)
        ]

        # Test getting all active executors
        active_executors = self.controller.get_active_executors()
        self.assertEqual(len(active_executors), 2)
        self.assertIn("exec1", [e.id for e in active_executors])
        self.assertIn("exec3", [e.id for e in active_executors])

        # Test getting active executors filtered by connector
        binance_active = self.controller.get_active_executors(connector_names=["binance"])
        self.assertEqual(len(binance_active), 2)

    def test_get_completed_executors(self):
        """Test get_completed_executors convenience method"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", status=RunnableStatus.RUNNING),
            self.create_mock_executor_info("exec2", status=RunnableStatus.TERMINATED),
            self.create_mock_executor_info("exec3", status=RunnableStatus.TERMINATED)
        ]

        # Test getting all completed executors
        completed_executors = self.controller.get_completed_executors()
        self.assertEqual(len(completed_executors), 2)
        self.assertIn("exec2", [e.id for e in completed_executors])
        self.assertIn("exec3", [e.id for e in completed_executors])

    def test_get_executors_by_type(self):
        """Test get_executors_by_type convenience method"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", executor_type="PositionExecutor"),
            self.create_mock_executor_info("exec2", executor_type="DCAExecutor"),
            self.create_mock_executor_info("exec3", executor_type="PositionExecutor")
        ]

        # Test getting executors by type
        position_executors = self.controller.get_executors_by_type(["PositionExecutor"])
        self.assertEqual(len(position_executors), 2)
        self.assertIn("exec1", [e.id for e in position_executors])
        self.assertIn("exec3", [e.id for e in position_executors])

    def test_get_executors_by_side(self):
        """Test get_executors_by_side convenience method"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", side=TradeType.BUY),
            self.create_mock_executor_info("exec2", side=TradeType.SELL),
            self.create_mock_executor_info("exec3", side=TradeType.BUY)
        ]

        # Test getting executors by side
        buy_executors = self.controller.get_executors_by_side([TradeType.BUY])
        self.assertEqual(len(buy_executors), 2)
        self.assertIn("exec1", [e.id for e in buy_executors])
        self.assertIn("exec3", [e.id for e in buy_executors])

    def test_open_orders_with_executor_filter(self):
        """Test open_orders method with ExecutorFilter"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", connector_name="binance", is_active=True),
            self.create_mock_executor_info("exec2", connector_name="coinbase", is_active=False),
            self.create_mock_executor_info("exec3", connector_name="binance", is_active=True)
        ]

        # Test getting open orders with filter
        executor_filter = ExecutorFilter(connector_names=["binance"])
        orders = self.controller.open_orders(executor_filter=executor_filter)
        self.assertEqual(len(orders), 2)  # Only active binance orders

        # Verify order information structure
        self.assertIn('executor_id', orders[0])
        self.assertIn('connector_name', orders[0])
        self.assertIn('trading_pair', orders[0])
        self.assertIn('side', orders[0])
        self.assertIn('type', orders[0])

    def test_open_orders_backward_compatibility(self):
        """Test open_orders method maintains backward compatibility"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", connector_name="binance", is_active=True),
            self.create_mock_executor_info("exec2", connector_name="coinbase", is_active=True)
        ]

        # Test old-style parameters still work
        orders = self.controller.open_orders(connector_name="binance")
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['executor_id'], "exec1")

    def test_cancel_all_with_executor_filter(self):
        """Test cancel_all method with ExecutorFilter"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", connector_name="binance", side=TradeType.BUY, is_active=True),
            self.create_mock_executor_info("exec2", connector_name="binance", side=TradeType.SELL, is_active=True),
            self.create_mock_executor_info("exec3", connector_name="coinbase", side=TradeType.BUY, is_active=True)
        ]

        # Mock the cancel method to always return True
        self.controller.cancel = MagicMock(return_value=True)

        # Test canceling with filter
        executor_filter = ExecutorFilter(sides=[TradeType.BUY])
        cancelled_ids = self.controller.cancel_all(executor_filter=executor_filter)

        self.assertEqual(len(cancelled_ids), 2)  # exec1 and exec3
        self.assertIn("exec1", cancelled_ids)
        self.assertIn("exec3", cancelled_ids)

        # Verify cancel was called for each executor
        self.assertEqual(self.controller.cancel.call_count, 2)

    def test_filter_executors_backward_compatibility(self):
        """Test filter_executors maintains backward compatibility with filter_func"""
        # Setup mock executors
        self.controller.executors_info = [
            self.create_mock_executor_info("exec1", connector_name="binance"),
            self.create_mock_executor_info("exec2", connector_name="coinbase"),
            self.create_mock_executor_info("exec3", connector_name="kraken")
        ]

        # Test old-style filter function still works
        def binance_filter(executor):
            return executor.connector_name == "binance"

        filtered = self.controller.filter_executors(filter_func=binance_filter)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].id, "exec1")

    # Tests for Trading API functionality

    def test_buy_market_order(self):
        """Test creating a market buy order."""
        # Mock market data provider
        self.mock_market_data_provider.time.return_value = 1640995200000
        self.mock_market_data_provider.get_price_by_type.return_value = Decimal("2000")
        self.mock_market_data_provider.ready = True

        executor_id = self.controller.buy(
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("0.1"),
            execution_strategy=ExecutionStrategy.MARKET
        )

        self.assertIsNotNone(executor_id)
        self.assertNotEqual(executor_id, "")

        # Check that action was added to queue using put_nowait
        self.mock_actions_queue.put_nowait.assert_called_once()
        # Verify the action is a CreateExecutorAction
        args = self.mock_actions_queue.put_nowait.call_args[0][0]
        self.assertEqual(len(args), 1)  # One action in the list

    def test_sell_limit_order(self):
        """Test creating a limit sell order."""
        # Mock market data provider
        self.mock_market_data_provider.time.return_value = 1640995200000
        self.mock_market_data_provider.ready = True

        executor_id = self.controller.sell(
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("0.1"),
            price=Decimal("2100"),
            execution_strategy=ExecutionStrategy.LIMIT_MAKER
        )

        self.assertIsNotNone(executor_id)
        self.assertNotEqual(executor_id, "")

        # Check that action was added to queue using put_nowait
        self.mock_actions_queue.put_nowait.assert_called_once()

    def test_buy_with_triple_barrier(self):
        """Test creating a buy order with triple barrier risk management."""
        # Mock market data provider
        self.mock_market_data_provider.time.return_value = 1640995200000
        self.mock_market_data_provider.ready = True

        triple_barrier = TripleBarrierConfig(
            stop_loss=Decimal("0.02"),
            take_profit=Decimal("0.03"),
            time_limit=300
        )

        executor_id = self.controller.buy(
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("0.1"),
            triple_barrier_config=triple_barrier
        )

        self.assertIsNotNone(executor_id)
        self.assertNotEqual(executor_id, "")

        # Check that action was added to queue using put_nowait
        self.mock_actions_queue.put_nowait.assert_called_once()

    def test_buy_with_limit_chaser(self):
        """Test creating a buy order with limit chaser strategy."""
        # Mock market data provider
        self.mock_market_data_provider.time.return_value = 1640995200000
        self.mock_market_data_provider.ready = True

        chaser_config = LimitChaserConfig(
            distance=Decimal("0.001"),
            refresh_threshold=Decimal("0.002")
        )

        executor_id = self.controller.buy(
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("0.1"),
            execution_strategy=ExecutionStrategy.LIMIT_CHASER,
            chaser_config=chaser_config
        )

        self.assertIsNotNone(executor_id)
        self.assertNotEqual(executor_id, "")

        # Check that action was added to queue using put_nowait
        self.mock_actions_queue.put_nowait.assert_called_once()

    def test_cancel_order(self):
        """Test canceling an order by executor ID."""
        # Setup mock executor
        mock_executor = self.create_mock_executor_info("test_executor_1", is_active=True)
        self.controller.executors_info = [mock_executor]

        # Test canceling existing executor
        result = self.controller.cancel("test_executor_1")
        self.assertTrue(result)

        # Check that action was added to queue using put_nowait
        self.mock_actions_queue.put_nowait.assert_called_once()

        # Reset mock
        self.mock_actions_queue.reset_mock()

        # Test canceling non-existent executor
        result = self.controller.cancel("non_existent")
        self.assertFalse(result)

        # Check that no action was added to queue
        self.mock_actions_queue.put_nowait.assert_not_called()

    def test_cancel_all_orders_trading_api(self):
        """Test canceling all orders with trading API."""
        # Setup mock executors
        mock_executor1 = self.create_mock_executor_info("test_executor_1", connector_name="binance", is_active=True)
        mock_executor2 = self.create_mock_executor_info("test_executor_2", connector_name="coinbase", is_active=True)
        self.controller.executors_info = [mock_executor1, mock_executor2]

        # Mock the cancel method to always return True
        self.controller.cancel = MagicMock(return_value=True)

        # Cancel all orders
        cancelled_ids = self.controller.cancel_all()
        self.assertEqual(len(cancelled_ids), 2)
        self.assertIn("test_executor_1", cancelled_ids)
        self.assertIn("test_executor_2", cancelled_ids)

        # Reset mock and test filters
        self.controller.cancel.reset_mock()

        # Cancel with connector filter
        cancelled_ids = self.controller.cancel_all(connector_name="binance")
        self.assertEqual(len(cancelled_ids), 1)
        self.assertIn("test_executor_1", cancelled_ids)

        # Cancel with non-matching filter
        cancelled_ids = self.controller.cancel_all(connector_name="kucoin")
        self.assertEqual(len(cancelled_ids), 0)

    def test_open_orders_trading_api(self):
        """Test getting open orders with trading API."""
        # Setup mock executor
        mock_executor = self.create_mock_executor_info(
            "test_executor_1",
            connector_name="binance",
            trading_pair="ETH-USDT",
            side=TradeType.BUY,
            is_active=True
        )
        mock_executor.filled_amount_quote = Decimal("0.1")
        mock_executor.status = RunnableStatus.RUNNING
        mock_executor.custom_info = {
            'connector_name': 'binance',
            'trading_pair': 'ETH-USDT',
            'side': TradeType.BUY
        }
        self.controller.executors_info = [mock_executor]

        orders = self.controller.open_orders()
        self.assertEqual(len(orders), 1)

        order = orders[0]
        self.assertEqual(order['executor_id'], "test_executor_1")
        self.assertEqual(order['connector_name'], 'binance')
        self.assertEqual(order['trading_pair'], 'ETH-USDT')
        self.assertEqual(order['side'], TradeType.BUY)
        self.assertEqual(order['amount'], Decimal("1.0"))  # From mock config
        self.assertEqual(order['filled_amount'], Decimal("0.1"))

    def test_open_orders_with_filters_trading_api(self):
        """Test getting open orders with filters in trading API."""
        # Setup mock executors
        mock_executor1 = self.create_mock_executor_info(
            "test_executor_1",
            connector_name="binance",
            trading_pair="ETH-USDT",
            is_active=True
        )
        mock_executor2 = self.create_mock_executor_info(
            "test_executor_2",
            connector_name="coinbase",
            trading_pair="BTC-USDT",
            is_active=True
        )
        self.controller.executors_info = [mock_executor1, mock_executor2]

        # Filter by connector
        orders = self.controller.open_orders(connector_name="binance")
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['executor_id'], "test_executor_1")

        # Filter by non-matching connector
        orders = self.controller.open_orders(connector_name="kucoin")
        self.assertEqual(len(orders), 0)

        # Filter by trading pair
        orders = self.controller.open_orders(trading_pair="ETH-USDT")
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['executor_id'], "test_executor_1")

    def test_get_current_price_trading_api(self):
        """Test getting current market price in trading API."""
        # Mock market data provider
        self.mock_market_data_provider.get_price_by_type.return_value = Decimal("2000")

        price = self.controller.get_current_price("binance", "ETH-USDT")
        self.assertEqual(price, Decimal("2000"))

        # Test with specific price type
        price = self.controller.get_current_price("binance", "ETH-USDT", PriceType.BestBid)
        self.assertEqual(price, Decimal("2000"))

        # Verify the mock was called correctly
        self.mock_market_data_provider.get_price_by_type.assert_called_with(
            "binance", "ETH-USDT", PriceType.BestBid
        )

    def test_find_executor_by_id_trading_api(self):
        """Test finding executor by ID in trading API."""
        # Setup mock executor
        mock_executor = self.create_mock_executor_info("test_executor_1")
        self.controller.executors_info = [mock_executor]

        executor = self.controller._find_executor_by_id("test_executor_1")
        self.assertIsNotNone(executor)
        self.assertEqual(executor.id, "test_executor_1")

        # Test non-existent executor
        executor = self.controller._find_executor_by_id("non_existent")
        self.assertIsNone(executor)
