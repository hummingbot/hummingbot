from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import MagicMock, PropertyMock, patch

from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import MarketOrderFailureEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.order_executor.data_types import (
    ExecutionStrategy,
    LimitChaserConfig,
    OrderExecutorConfig,
)
from hummingbot.strategy_v2.executors.order_executor.order_executor import OrderExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class TestOrderExecutor(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    def setUp(self) -> None:
        super().setUp()
        self.strategy = self.create_mock_strategy()
        self.update_interval = 0.5

    @staticmethod
    def create_mock_strategy():
        market = MagicMock()
        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock(spec=ScriptStrategyBase)
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="ETH-USDT")
        strategy.buy.side_effect = ["OID-BUY-1", "OID-BUY-2", "OID-BUY-3"]
        strategy.sell.side_effect = ["OID-SELL-1", "OID-SELL-2", "OID-SELL-3"]
        strategy.cancel.return_value = None
        connector = MagicMock(spec=ExchangePyBase)
        type(connector).trading_rules = PropertyMock(return_value={"ETH-USDT": TradingRule(trading_pair="ETH-USDT")})
        strategy.connectors = {
            "binance": connector,
        }
        return strategy

    def get_order_executor_from_config(self, config: OrderExecutorConfig):
        executor = OrderExecutor(self.strategy, config, self.update_interval)
        self.set_loggers(loggers=[executor.logger()])
        return executor

    @patch.object(OrderExecutor, "get_price", MagicMock(return_value=Decimal("120")))
    async def test_control_task_market_order(self):
        config = OrderExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price=Decimal("100"),
            execution_strategy=ExecutionStrategy.MARKET
        )
        executor = self.get_order_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        await executor.control_task()
        self.assertEqual(executor._order.order_id, "OID-BUY-1")

    @patch.object(OrderExecutor, "get_price", MagicMock(return_value=Decimal("120")))
    async def test_control_task_limit_maker_order(self):
        config = OrderExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price=Decimal("100"),
            execution_strategy=ExecutionStrategy.LIMIT_MAKER
        )
        executor = self.get_order_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        await executor.control_task()
        self.assertEqual(executor._order.order_id, "OID-BUY-1")

    @patch.object(OrderExecutor, "get_price", MagicMock(return_value=Decimal("120")))
    async def test_control_task_limit_chaser_order(self):
        config = OrderExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price=Decimal("100"),
            execution_strategy=ExecutionStrategy.LIMIT_CHASER,
            chaser_config=LimitChaserConfig(distance=Decimal("0.01"), refresh_threshold=Decimal("0.02"))
        )
        executor = self.get_order_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        await executor.control_task()
        self.assertEqual(executor._order.order_id, "OID-BUY-1")

    def test_process_order_failed_event(self):
        config = OrderExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price=Decimal("100"),
            execution_strategy=ExecutionStrategy.MARKET
        )
        executor = self.get_order_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        # Simulate an order
        order_id = "OID-FAIL"
        order = InFlightOrder(
            client_order_id=order_id,
            trading_pair=config.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=config.side,
            price=Decimal("100"),
            amount=Decimal("1"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN
        )
        tracked_order = TrackedOrder(order_id)
        tracked_order.order = order
        executor._order = tracked_order

        # Trigger the order failed event
        failure_event = MarketOrderFailureEvent(
            order_id=order_id,
            timestamp=1640001112.223,
            order_type=OrderType.MARKET
        )
        executor.process_order_failed_event(1, self.strategy.connectors["binance"], failure_event)

        # Assertions
        self.assertIn(tracked_order, executor._failed_orders)
        self.assertIsNone(executor._order)
        self.assertEqual(executor._current_retries, 1)

    @patch.object(OrderExecutor, "get_in_flight_order")
    def test_process_order_completed_event(self, in_flight_order_mock):
        # Create the order that will be returned by get_in_flight_order
        order = InFlightOrder(
            client_order_id="OID-COMPLETE",
            exchange_order_id="EOID4",
            trading_pair="ETH-USDT",
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.COMPLETED
        )
        in_flight_order_mock.return_value = order

        # Setup executor
        config = OrderExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price=Decimal("100"),
            execution_strategy=ExecutionStrategy.MARKET
        )
        executor = self.get_order_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        executor._order = TrackedOrder("OID-COMPLETE")

        # Create and process the completed event
        from hummingbot.core.event.events import BuyOrderCompletedEvent
        completed_event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-COMPLETE",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=config.amount,
            quote_asset_amount=config.amount * config.price,
            order_type=OrderType.MARKET,
            exchange_order_id="EOID4"
        )
        market = MagicMock()
        executor.process_order_completed_event("102", market, completed_event)

        # Assertions
        self.assertEqual(executor._order.order, order)
        self.assertEqual(executor._status, RunnableStatus.TERMINATED)
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(len(executor._held_position_orders), 1)

    def test_get_custom_info(self):
        config = OrderExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price=Decimal("100"),
            execution_strategy=ExecutionStrategy.MARKET
        )
        executor = self.get_order_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        # Simulate an order
        order_id = "OID-INFO"
        order = InFlightOrder(
            client_order_id=order_id,
            trading_pair=config.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=config.side,
            price=Decimal("100"),
            amount=Decimal("1"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN
        )
        tracked_order = TrackedOrder(order_id)
        tracked_order.order = order
        executor._order = tracked_order

        custom_info = executor.get_custom_info()
        self.assertEqual(custom_info["level_id"], None)
        self.assertEqual(custom_info["current_retries"], 0)
        self.assertEqual(custom_info["max_retries"], 10)
        self.assertEqual(custom_info["order_id"], "OID-INFO")
        self.assertEqual(custom_info["held_position_orders"], [])

    def test_to_format_status(self):
        config = OrderExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price=Decimal("100"),
            execution_strategy=ExecutionStrategy.MARKET
        )
        executor = self.get_order_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        # Simulate an order
        order_id = "OID-STATUS"
        order = InFlightOrder(
            client_order_id=order_id,
            trading_pair=config.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=config.side,
            price=Decimal("100"),
            amount=Decimal("1"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN
        )
        tracked_order = TrackedOrder(order_id)
        tracked_order.order = order
        executor._order = tracked_order

        status_lines = executor.to_format_status()
        self.assertEqual(len(status_lines), 1)
        self.assertIn("Trading Pair: ETH-USDT", status_lines[0])
        self.assertIn("Exchange: binance", status_lines[0])
        self.assertIn("Amount: 1", status_lines[0])
        self.assertIn("Price: 100", status_lines[0])
        self.assertIn("Execution Strategy: ExecutionStrategy.MARKET", status_lines[0])
        self.assertIn("Retries: 0/10", status_lines[0])

    async def test_pnl_metrics_zero(self):
        config = OrderExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price=Decimal("100"),
            execution_strategy=ExecutionStrategy.MARKET
        )
        executor = self.get_order_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        self.assertEqual(executor.net_pnl_pct, Decimal("0"))
        self.assertEqual(executor.net_pnl_quote, Decimal("0"))
        self.assertEqual(executor.cum_fees_quote, Decimal("0"))

    @patch.object(OrderExecutor, 'get_trading_rules')
    @patch.object(OrderExecutor, 'adjust_order_candidates')
    async def test_validate_sufficient_balance(self, mock_adjust_order_candidates, mock_get_trading_rules):
        # Mock trading rules
        trading_rules = TradingRule(trading_pair="ETH-USDT", min_order_size=Decimal("0.1"),
                                    min_price_increment=Decimal("0.1"), min_base_amount_increment=Decimal("0.1"))
        mock_get_trading_rules.return_value = trading_rules
        config = OrderExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price=Decimal("100"),
            execution_strategy=ExecutionStrategy.MARKET
        )
        executor = self.get_order_executor_from_config(config)
        # Mock order candidate
        order_candidate = OrderCandidate(
            trading_pair="ETH-USDT",
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100")
        )
        # Test for sufficient balance
        mock_adjust_order_candidates.return_value = [order_candidate]
        await executor.validate_sufficient_balance()
        self.assertNotEqual(executor.close_type, CloseType.INSUFFICIENT_BALANCE)

        # Test for insufficient balance
        order_candidate.amount = Decimal("0")
        mock_adjust_order_candidates.return_value = [order_candidate]
        await executor.validate_sufficient_balance()
        self.assertEqual(executor.close_type, CloseType.INSUFFICIENT_BALANCE)
        self.assertEqual(executor.status, RunnableStatus.TERMINATED)

    @patch.object(OrderExecutor, 'get_trading_rules')
    @patch.object(OrderExecutor, 'adjust_order_candidates')
    async def test_validate_sufficient_balance_perpetual(self, mock_adjust_order_candidates, mock_get_trading_rules):
        # Mock trading rules
        trading_rules = TradingRule(trading_pair="ETH-USDT", min_order_size=Decimal("0.1"),
                                    min_price_increment=Decimal("0.1"), min_base_amount_increment=Decimal("0.1"))
        mock_get_trading_rules.return_value = trading_rules
        config = OrderExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance_perpetual",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price=Decimal("100"),
            execution_strategy=ExecutionStrategy.MARKET
        )
        executor = self.get_order_executor_from_config(config)
        # Mock order candidate
        order_candidate = OrderCandidate(
            trading_pair="ETH-USDT",
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100")
        )
        # Test for sufficient balance
        mock_adjust_order_candidates.return_value = [order_candidate]
        await executor.validate_sufficient_balance()
        self.assertNotEqual(executor.close_type, CloseType.INSUFFICIENT_BALANCE)

        # Test for insufficient balance
        order_candidate.amount = Decimal("0")
        mock_adjust_order_candidates.return_value = [order_candidate]
        await executor.validate_sufficient_balance()
        self.assertEqual(executor.close_type, CloseType.INSUFFICIENT_BALANCE)
        self.assertEqual(executor.status, RunnableStatus.TERMINATED)
