from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import MagicMock, PropertyMock, patch

import pandas as pd

from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import MarketOrderFailureEvent, OrderCancelledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.best_price_executor.best_price_executor import BestPriceExecutor
from hummingbot.strategy_v2.executors.best_price_executor.data_types import BestPriceExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class TestBestPriceExecutor(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
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

        # Mock order book
        order_book = MagicMock()
        bids_df = pd.DataFrame({
            'price': [Decimal('100.0'), Decimal('99.9'), Decimal('99.8')],
            'amount': [Decimal('1.0'), Decimal('2.0'), Decimal('3.0')]
        })
        asks_df = pd.DataFrame({
            'price': [Decimal('100.1'), Decimal('100.2'), Decimal('100.3')],
            'amount': [Decimal('1.0'), Decimal('2.0'), Decimal('3.0')]
        })
        order_book.snapshot = (bids_df, asks_df)
        connector.get_order_book.return_value = order_book

        strategy.connectors = {
            "binance": connector
        }
        return strategy

    def get_best_price_executor_from_config(self, config: BestPriceExecutorConfig):
        executor = BestPriceExecutor(self.strategy, config, self.update_interval)
        self.set_loggers(loggers=[executor.logger()])
        return executor

    @patch.object(BestPriceExecutor, "get_price", MagicMock(return_value=Decimal("100.0")))
    async def test_control_task_places_order(self):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING
        await executor.control_task()
        self.assertEqual(executor._order.order_id, "OID-BUY-1")

    @patch.object(BestPriceExecutor, "get_price", MagicMock(return_value=Decimal("100.0")))
    def test_compute_best_price_buy(self):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
        best_price = executor._compute_best_price()
        # For BUY: best_price + price_diff
        self.assertEqual(best_price, Decimal("100.1"))

    @patch.object(BestPriceExecutor, "get_price", MagicMock(return_value=Decimal("100.1")))
    def test_compute_best_price_sell(self):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.SELL,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
        best_price = executor._compute_best_price()
        # For SELL: best_price - price_diff
        self.assertEqual(best_price, Decimal("100.0"))

    def test_get_nth_level_price_buy(self):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)

        # Test getting best bid (level 0)
        price = executor._get_nth_level_price(0)
        self.assertEqual(price, Decimal("100.0"))

        # Test getting second level bid
        price = executor._get_nth_level_price(1)
        self.assertEqual(price, Decimal("99.9"))

    def test_get_nth_level_price_sell(self):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.SELL,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)

        # Test getting best ask (level 0)
        price = executor._get_nth_level_price(0)
        self.assertEqual(price, Decimal("100.1"))

        # Test getting second level ask
        price = executor._get_nth_level_price(1)
        self.assertEqual(price, Decimal("100.2"))

    def test_process_order_failed_event(self):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        # Simulate an order
        order_id = "OID-FAIL"
        order = InFlightOrder(
            client_order_id=order_id,
            trading_pair=config.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
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
            order_type=OrderType.LIMIT_MAKER
        )
        executor.process_order_failed_event(1, self.strategy.connectors["binance"], failure_event)

        # Assertions
        self.assertIn(tracked_order, executor._failed_orders)
        self.assertIsNone(executor._order)

    @patch.object(BestPriceExecutor, "get_in_flight_order")
    def test_process_order_completed_event(self, in_flight_order_mock):
        # Create the order that will be returned by get_in_flight_order
        order = InFlightOrder(
            client_order_id="OID-COMPLETE",
            exchange_order_id="EOID4",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT_MAKER,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.COMPLETED
        )
        in_flight_order_mock.return_value = order

        # Setup executor
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
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
            quote_asset_amount=config.amount * Decimal("100"),
            order_type=OrderType.LIMIT_MAKER,
            exchange_order_id="EOID4"
        )
        market = MagicMock()
        executor.process_order_completed_event("102", market, completed_event)

        # Assertions
        self.assertEqual(executor._status, RunnableStatus.TERMINATED)
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(len(executor._held_position_orders), 1)

    def test_process_order_canceled_event(self):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        # Simulate an order
        order_id = "OID-CANCEL"
        order = InFlightOrder(
            client_order_id=order_id,
            trading_pair=config.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
            trade_type=config.side,
            price=Decimal("100"),
            amount=Decimal("1"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN
        )
        tracked_order = TrackedOrder(order_id)
        tracked_order.order = order
        executor._order = tracked_order

        # Trigger the order canceled event
        cancel_event = OrderCancelledEvent(
            order_id=order_id,
            timestamp=1640001112.223,
            exchange_order_id="EOID1"
        )
        market = MagicMock()
        executor.process_order_canceled_event(1, market, cancel_event)

        # Assertions
        self.assertIn(tracked_order, executor._canceled_orders)
        self.assertIsNone(executor._order)

    def test_process_order_canceled_event_with_partial_fill(self):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        # Simulate a partially filled order
        order_id = "OID-PARTIAL-CANCEL"
        order = InFlightOrder(
            client_order_id=order_id,
            trading_pair=config.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
            trade_type=config.side,
            price=Decimal("100"),
            amount=Decimal("1"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.PARTIALLY_FILLED
        )
        order.executed_amount_base = Decimal("0.5")
        tracked_order = TrackedOrder(order_id)
        tracked_order.order = order
        executor._order = tracked_order

        # Trigger the order canceled event
        cancel_event = OrderCancelledEvent(
            order_id=order_id,
            timestamp=1640001112.223,
            exchange_order_id="EOID2"
        )
        market = MagicMock()
        executor.process_order_canceled_event(1, market, cancel_event)

        # Assertions
        self.assertIn(tracked_order, executor._partial_filled_orders)
        self.assertIsNone(executor._order)

    def test_get_custom_info(self):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
            level_id="level_1",
        )
        executor = self.get_best_price_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        # Simulate an order
        order_id = "OID-INFO"
        order = InFlightOrder(
            client_order_id=order_id,
            trading_pair=config.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
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
        self.assertEqual(custom_info["level_id"], "level_1")
        self.assertEqual(custom_info["order_id"], "OID-INFO")
        self.assertEqual(custom_info["price_diff"], Decimal("0.1"))
        self.assertEqual(custom_info["held_position_orders"], [])

    def test_to_format_status(self):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
            position_action=PositionAction.OPEN,
        )
        executor = self.get_best_price_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        # Simulate an order
        order_id = "OID-STATUS"
        order = InFlightOrder(
            client_order_id=order_id,
            trading_pair=config.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
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
        self.assertIn("Strategy: BEST_PRICE", status_lines[0])
        self.assertIn("Price Diff: 0.1", status_lines[0])

    async def test_pnl_metrics_zero(self):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        self.assertEqual(executor.net_pnl_pct, Decimal("0"))
        self.assertEqual(executor.net_pnl_quote, Decimal("0"))
        self.assertEqual(executor.cum_fees_quote, Decimal("0"))

    @patch.object(BestPriceExecutor, 'get_trading_rules')
    @patch.object(BestPriceExecutor, 'adjust_order_candidates')
    async def test_validate_sufficient_balance(self, mock_adjust_order_candidates, mock_get_trading_rules):
        # Mock trading rules
        trading_rules = TradingRule(trading_pair="ETH-USDT", min_order_size=Decimal("0.1"),
                                    min_price_increment=Decimal("0.1"), min_base_amount_increment=Decimal("0.1"))
        mock_get_trading_rules.return_value = trading_rules
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
        # Mock order candidate
        order_candidate = OrderCandidate(
            trading_pair="ETH-USDT",
            is_maker=True,
            order_type=OrderType.LIMIT_MAKER,
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

    @patch.object(BestPriceExecutor, '_sleep')
    async def test_control_shutdown_process_with_open_order(self, mock_sleep):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
        executor._status = RunnableStatus.SHUTTING_DOWN

        # Create an open order
        order = InFlightOrder(
            client_order_id="OID-OPEN",
            trading_pair=config.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
            trade_type=config.side,
            price=Decimal("100"),
            amount=Decimal("1"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN
        )
        executor._order = TrackedOrder("OID-OPEN")
        executor._order.order = order

        await executor.control_shutdown_process()
        mock_sleep.assert_called_once_with(5.0)
        self.strategy.cancel.assert_called_once_with(
            connector_name=config.connector_name,
            trading_pair=config.trading_pair,
            order_id="OID-OPEN"
        )

    @patch.object(BestPriceExecutor, '_sleep')
    async def test_control_shutdown_process_with_filled_order(self, mock_sleep):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
        executor._status = RunnableStatus.SHUTTING_DOWN

        # Create a filled order
        order = InFlightOrder(
            client_order_id="OID-FILLED",
            trading_pair=config.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
            trade_type=config.side,
            price=Decimal("100"),
            amount=Decimal("1"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.FILLED
        )
        executor._order = TrackedOrder("OID-FILLED")
        executor._order.order = order

        await executor.control_shutdown_process()
        mock_sleep.assert_called_once_with(5.0)
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(len(executor._held_position_orders), 1)
        self.assertEqual(executor.status, RunnableStatus.TERMINATED)

    @patch.object(BestPriceExecutor, '_sleep')
    async def test_control_shutdown_process_with_partial_filled_orders(self, mock_sleep):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
        executor._status = RunnableStatus.SHUTTING_DOWN

        # Create a partially filled order
        order = InFlightOrder(
            client_order_id="OID-PARTIAL",
            trading_pair=config.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
            trade_type=config.side,
            price=Decimal("100"),
            amount=Decimal("1"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.PARTIALLY_FILLED
        )
        tracked_order = TrackedOrder("OID-PARTIAL")
        tracked_order.order = order
        executor._partial_filled_orders = [tracked_order]

        await executor.control_shutdown_process()
        mock_sleep.assert_called_once_with(5.0)
        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(len(executor._held_position_orders), 1)
        self.assertEqual(executor.status, RunnableStatus.TERMINATED)

    @patch.object(BestPriceExecutor, "get_price")
    @patch.object(BestPriceExecutor, "_get_nth_level_price")
    async def test_maintain_best_price_position_renews_order(self, mock_nth_level, mock_get_price):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        # Create an order at price 100.1
        order = InFlightOrder(
            client_order_id="OID-RENEW",
            trading_pair=config.trading_pair,
            order_type=OrderType.LIMIT_MAKER,
            trade_type=config.side,
            price=Decimal("100.1"),
            amount=Decimal("1"),
            creation_timestamp=1640001112.223,
            initial_state=OrderState.OPEN
        )
        tracked_order = TrackedOrder("OID-RENEW")
        tracked_order.order = order
        executor._order = tracked_order

        # Mock best price changed to 100.2
        mock_get_price.return_value = Decimal("100.2")
        mock_nth_level.return_value = None

        # Call maintain_best_price_position
        executor.maintain_best_price_position()

        # Verify that renew_order was initiated (renewal_task created)
        self.assertIsNotNone(executor._renewal_task)

    def test_early_stop(self):
        config = BestPriceExecutorConfig(
            id="test",
            timestamp=123,
            side=TradeType.BUY,
            connector_name="binance",
            trading_pair="ETH-USDT",
            amount=Decimal("1"),
            price_diff=Decimal("0.1"),
        )
        executor = self.get_best_price_executor_from_config(config)
        executor._status = RunnableStatus.RUNNING

        executor.early_stop()
        self.assertEqual(executor.status, RunnableStatus.SHUTTING_DOWN)
