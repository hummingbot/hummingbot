from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
)
from hummingbot.strategy.strategy_v2_base import StrategyV2Base
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase, sanitize_non_finite_decimals
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType


class TestExecutorBase(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    def setUp(self):
        self.strategy = self.create_mock_strategy
        self.config = ExecutorConfigBase(id="test", type="position_executor", timestamp=1234567890)
        self.component = ExecutorBase(strategy=self.strategy, connectors=["connector1"], config=self.config,
                                      update_interval=0.5)

    @property
    def create_mock_strategy(self):
        market = MagicMock()
        market_info = MagicMock()
        market_info.market = market

        strategy = MagicMock(spec=StrategyV2Base)
        type(strategy).market_info = PropertyMock(return_value=market_info)
        type(strategy).trading_pair = PropertyMock(return_value="ETH-USDT")
        strategy.buy.side_effect = ["OID-BUY-1", "OID-BUY-2", "OID-BUY-3"]
        strategy.sell.side_effect = ["OID-SELL-1", "OID-SELL-2", "OID-SELL-3"]
        strategy.cancel.return_value = None
        connector = MagicMock(spec=ExchangePyBase)
        connector.get_price_by_type.return_value = Decimal("1000.0")
        connector.get_order_book.return_value = OrderBook()
        connector.get_balance.return_value = Decimal("0.0")
        connector.get_available_balance.return_value = Decimal("0.0")
        connector._order_tracker = MagicMock(spec=ClientOrderTracker)
        connector._order_tracker.fetch_order.return_value = None
        strategy.connectors = {
            "connector1": connector,
        }
        return strategy

    def test_process_order_completed_event(self):
        event_tag = 1
        market = MagicMock()
        event = BuyOrderCompletedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            base_asset="ETH",
            quote_asset="USDT",
            base_asset_amount=Decimal("1.0"),
            quote_asset_amount=Decimal("1.0") * Decimal("1000.0"),
            order_type=OrderType.LIMIT,
            exchange_order_id="ED140"
        )
        self.component.process_order_completed_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_completed_event(event_tag, market, event))

    def test_process_order_created_event(self):
        event_tag = 1
        market = MagicMock()
        event = BuyOrderCreatedEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            trading_pair="ETH-USDT",
            amount=Decimal("1.0"),
            type=OrderType.LIMIT,
            price=Decimal("1000.0"),
            exchange_order_id="ED140",
            creation_timestamp=1234567890
        )
        self.component.process_order_created_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_created_event(event_tag, market, event))

    def test_process_order_canceled_event(self):
        event_tag = 1
        market = MagicMock()
        event = OrderCancelledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            exchange_order_id="ED140",
        )
        self.component.process_order_canceled_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_canceled_event(event_tag, market, event))

    def test_process_order_filled_event(self):
        event_tag = 1
        market = MagicMock()
        event = OrderFilledEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            exchange_order_id="ED140",
            trading_pair="ETH-USDT",
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("1000.0"),
            amount=Decimal("1.0"),
            trade_fee=AddedToCostTradeFee(percent=Decimal("0.001")),
        )
        self.component.process_order_filled_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_filled_event(event_tag, market, event))

    def test_process_order_failed_event(self):
        event_tag = 1
        market = MagicMock()
        event = MarketOrderFailureEvent(
            timestamp=1234567890,
            order_id="OID-BUY-1",
            order_type=OrderType.LIMIT,
        )
        self.component.process_order_failed_event(event_tag, market, event)
        self.assertIsNone(self.component.process_order_failed_event(event_tag, market, event))

    def test_place_buy_order(self):
        buy_order_id = self.component.place_order(
            connector_name="connector1",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT,
            side=TradeType.BUY,
            price=Decimal("1000.0"),
            amount=Decimal("1.0"),
        )
        self.assertEqual(buy_order_id, "OID-BUY-1")

    def test_place_sell_order(self):
        sell_order_id = self.component.place_order(
            connector_name="connector1",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT,
            side=TradeType.SELL,
            price=Decimal("1000.0"),
            amount=Decimal("1.0"),
        )
        self.assertEqual(sell_order_id, "OID-SELL-1")

    async def test_executor_starts_and_stops(self):
        self.assertEqual(RunnableStatus.NOT_STARTED, self.component.status)
        self.component.start()
        self.assertEqual(RunnableStatus.RUNNING, self.component.status)
        self.component.stop()
        self.assertEqual(RunnableStatus.TERMINATED, self.component.status)

    def test_get_price_by_type(self):
        price = self.component.get_price("connector1", "EHT-USDT", PriceType.MidPrice)
        self.assertEqual(price, Decimal("1000.0"))

    def test_get_order_book(self):
        order_book = self.component.get_order_book("connector1", "ETH-USDT")
        self.assertEqual(order_book.last_diff_uid, 0)

    def test_get_total_and_available_balance(self):
        balance = self.component.get_balance("connector1", "ETH")
        self.assertEqual(balance, Decimal("0.0"))
        available_balance = self.component.get_available_balance("connector1", "ETH")
        self.assertEqual(available_balance, Decimal("0.0"))

    def test_get_in_flight_order(self):
        in_flight_orders = self.component.get_in_flight_order("connector1", "OID-BUY-1")
        self.assertEqual(in_flight_orders, None)

    async def test_control_loop_calls_control_task_and_evaluate_max_retries(self):
        """Test that control_loop calls control_task and evaluate_max_retries, then sleeps."""
        call_count = 0

        async def mock_control_task():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                self.component.stop()

        with patch.object(self.component, "control_task", side_effect=mock_control_task), \
             patch.object(self.component, "evaluate_max_retries") as mock_eval, \
             patch.object(self.component, "validate_sufficient_balance", new_callable=AsyncMock), \
             patch.object(self.component, "on_stop"):
            self.component.update_interval = 0.01
            await self.component.control_loop()
            self.assertGreaterEqual(call_count, 2)
            self.assertGreaterEqual(mock_eval.call_count, 1)

    async def test_control_loop_handles_exception_in_control_task(self):
        """Test that control_loop catches exceptions from control_task and continues."""
        call_count = 0

        async def mock_control_task():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("test error")
            self.component.stop()

        with patch.object(self.component, "control_task", side_effect=mock_control_task), \
             patch.object(self.component, "evaluate_max_retries"), \
             patch.object(self.component, "validate_sufficient_balance", new_callable=AsyncMock), \
             patch.object(self.component, "on_stop"):
            self.component.update_interval = 0.01
            self.component.terminated.clear()
            await self.component.control_loop()
            self.assertGreaterEqual(call_count, 2)

    async def test_control_loop_closes_executor_when_on_start_raises(self):
        """A failure in on_start must terminate the executor, not strand it.

        on_start runs before the loop's own try/except, so an exception there used to
        escape control_loop entirely: the executor was never terminated and kept
        reporting RUNNING with no close_type while nothing ticked it again.
        """
        self.component._strategy.current_timestamp = 1234567890
        failing_start = AsyncMock(side_effect=RuntimeError("cannot price this market"))
        with patch.object(self.component, "control_task", new_callable=AsyncMock) as mock_task, \
             patch.object(self.component, "validate_sufficient_balance", failing_start), \
             patch.object(self.component, "on_stop") as mock_on_stop:
            self.component.update_interval = 0.01
            self.component.terminated.clear()
            await self.component.control_loop()

        self.assertEqual(self.component.close_type, CloseType.FAILED)
        self.assertEqual(self.component.status, RunnableStatus.TERMINATED)
        self.assertTrue(self.component.terminated.is_set())
        # The loop body must never run once startup failed.
        mock_task.assert_not_called()
        mock_on_stop.assert_called_once()

    async def test_evaluate_max_retries_sets_failed_close_type(self):
        """Test that evaluate_max_retries sets CloseType.FAILED when retries exceeded."""
        self.component._current_retries = 11
        self.component._max_retries = 10
        self.component._strategy.current_timestamp = 1234567890
        self.component.evaluate_max_retries()
        self.assertEqual(self.component.close_type, CloseType.FAILED)
        self.assertEqual(self.component.status, RunnableStatus.TERMINATED)

    def test_force_stop_with_position_hold_uses_accumulated_orders(self):
        """The default collector hands over whatever a normal shutdown already accumulated."""
        self.set_loggers(loggers=[self.component.logger()])
        held = [{"client_order_id": "OID-HELD"}]
        self.component._held_position_orders = list(held)

        self.component.force_stop_with_position_hold()

        self.assertEqual(self.component.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(self.component.status, RunnableStatus.TERMINATED)
        self.assertEqual(self.component._held_position_orders, held)

    def test_force_stop_with_position_hold_without_exposure_fails_visibly(self):
        """Nothing executed means nothing to hold — the abnormal end must stay visible."""
        self.set_loggers(loggers=[self.component.logger()])
        self.component.force_stop_with_position_hold()

        self.assertEqual(self.component.close_type, CloseType.FAILED)
        self.assertEqual(self.component.status, RunnableStatus.TERMINATED)

    def test_force_stop_with_position_hold_survives_cancel_failure(self):
        """Exposure must still be persisted when order cancellation is already unavailable."""
        self.set_loggers(loggers=[self.component.logger()])
        self.component._held_position_orders = [{"client_order_id": "OID-HELD"}]
        with patch.object(self.component, "_cancel_outstanding_orders", side_effect=RuntimeError("strategy stopped")):
            self.component.force_stop_with_position_hold()

        self.assertEqual(self.component.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(self.component.status, RunnableStatus.TERMINATED)
        self.assertTrue(self.is_partially_logged("ERROR", "Failed to cancel outstanding orders during forced stop."))


class TestSanitizeNonFiniteDecimals(IsolatedAsyncioWrapperTestCase):
    """Guards issue #7330: non-finite Decimals in custom_info must not reach persistence."""

    def test_replaces_nan_and_inf_with_zero(self):
        self.assertEqual(sanitize_non_finite_decimals(Decimal("NaN")), Decimal("0"))
        self.assertEqual(sanitize_non_finite_decimals(Decimal("Infinity")), Decimal("0"))
        self.assertEqual(sanitize_non_finite_decimals(Decimal("-Infinity")), Decimal("0"))

    def test_preserves_finite_decimals_and_other_types(self):
        self.assertEqual(sanitize_non_finite_decimals(Decimal("1.5")), Decimal("1.5"))
        self.assertEqual(sanitize_non_finite_decimals("NaN"), "NaN")  # a plain string is untouched
        self.assertEqual(sanitize_non_finite_decimals(3), 3)
        self.assertIsNone(sanitize_non_finite_decimals(None))

    def test_recurses_into_dicts_lists_and_tuples(self):
        raw = {
            "price": Decimal("NaN"),
            "orders": [Decimal("Infinity"), Decimal("2.0")],
            "meta": {"pct": Decimal("-Infinity")},
            "pair": (Decimal("NaN"), "AVAX-USDC"),
        }
        cleaned = sanitize_non_finite_decimals(raw)
        self.assertEqual(cleaned["price"], Decimal("0"))
        self.assertEqual(cleaned["orders"], [Decimal("0"), Decimal("2.0")])
        self.assertEqual(cleaned["meta"]["pct"], Decimal("0"))
        self.assertEqual(cleaned["pair"], (Decimal("0"), "AVAX-USDC"))
