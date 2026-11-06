"""An executor that gives up must not report that it left nothing behind.

Every path here ends the executor, and the question each one answers is the same: is
there filled quantity sitting in the account? `CloseType.FAILED` says no. So a retry
budget exhausted after a partial fill, or an order stuck in an indeterminate state at
shutdown, has to terminate `POSITION_HOLD` carrying those fills — the base
FAILED-and-stop would drop real exposure out of the store silently.
"""
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock, patch

from hummingbot.core.data_type.common import PositionAction, TradeType
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.executors.order_executor.order_executor import OrderExecutor
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


def a_config(**overrides) -> OrderExecutorConfig:
    fields = dict(
        id="test-terminal",
        timestamp=1234567890,
        connector_name="binance",
        trading_pair="ETH-USDT",
        side=TradeType.BUY,
        amount=Decimal("1"),
        execution_strategy=ExecutionStrategy.MARKET,
        position_action=PositionAction.OPEN,
    )
    fields.update(overrides)
    return OrderExecutorConfig(**fields)


def a_tracked_order(order_id="o-1", filled=Decimal("0"), is_filled=False, is_open=False):
    tracked = TrackedOrder(order_id=order_id)
    order = MagicMock()
    order.order_id = order_id
    order.client_order_id = order_id
    order.executed_amount_base = filled
    order.is_filled = is_filled
    order.is_open = is_open
    order.is_pending_cancel_confirmation = False
    order.to_json.return_value = {"client_order_id": order_id, "executed_amount_base": float(filled)}
    tracked.order = order
    return tracked


class TestRetryExhaustion(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890

    def an_executor(self) -> OrderExecutor:
        executor = OrderExecutor(self.strategy, a_config(), update_interval=1.0)
        executor.stop = MagicMock()
        return executor

    def test_exhausting_retries_with_nothing_filled_is_a_plain_failure(self):
        executor = self.an_executor()
        executor._current_retries = executor._max_retries + 1

        executor.evaluate_max_retries()

        self.assertEqual(executor.close_type, CloseType.FAILED)
        executor.stop.assert_called_once()

    def test_exhausting_retries_after_a_partial_fill_holds_the_position(self):
        """The case the base class gets wrong: filled quantity is real exposure."""
        executor = self.an_executor()
        executor._partial_filled_orders = [a_tracked_order("partial", filled=Decimal("0.4"))]
        executor._current_retries = executor._max_retries + 1

        executor.evaluate_max_retries()

        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(len(executor._held_position_orders), 1)

    def test_a_filled_active_order_is_carried_into_the_hold(self):
        executor = self.an_executor()
        executor._order = a_tracked_order("filled", filled=Decimal("1"), is_filled=True)
        executor._current_retries = executor._max_retries + 1

        executor.evaluate_max_retries()

        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(executor._held_position_orders[0]["client_order_id"], "filled")

    def test_within_budget_nothing_terminates(self):
        executor = self.an_executor()
        executor._current_retries = 0

        executor.evaluate_max_retries()

        self.assertIsNone(executor.close_type)
        executor.stop.assert_not_called()


class TestOrderFailedEvent(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890

    def an_executor(self) -> OrderExecutor:
        return OrderExecutor(self.strategy, a_config(), update_interval=1.0)

    def test_a_failure_after_a_partial_fill_keeps_the_fill(self):
        """It counts toward executed_amount_base and toward the terminal hold; treating
        it as a plain failure would drop quantity the account actually holds."""
        executor = self.an_executor()
        executor._order = a_tracked_order("o-1", filled=Decimal("0.3"))
        event = MagicMock(order_id="o-1")

        executor.process_order_failed_event("tag", MagicMock(), event)

        self.assertEqual(len(executor._partial_filled_orders), 1)
        self.assertEqual(len(executor._failed_orders), 0)
        self.assertIsNone(executor._order)

    def test_a_failure_with_no_fill_is_just_a_failed_order(self):
        executor = self.an_executor()
        executor._order = a_tracked_order("o-1", filled=Decimal("0"))
        event = MagicMock(order_id="o-1")

        executor.process_order_failed_event("tag", MagicMock(), event)

        self.assertEqual(len(executor._failed_orders), 1)
        self.assertEqual(len(executor._partial_filled_orders), 0)

    def test_a_failure_for_someone_elses_order_is_ignored(self):
        executor = self.an_executor()
        executor._order = a_tracked_order("mine", filled=Decimal("0"))

        executor.process_order_failed_event("tag", MagicMock(), MagicMock(order_id="not-mine"))

        self.assertIsNotNone(executor._order)
        self.assertEqual(len(executor._failed_orders), 0)


class TestShutdownWithAnIndeterminateOrder(IsolatedAsyncioWrapperTestCase):
    """Neither open nor filled — usually a created event that never arrived. Waiting
    forever in SHUTTING_DOWN is the failure mode this bounds."""

    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890

    def an_executor(self) -> OrderExecutor:
        executor = OrderExecutor(self.strategy, a_config(), update_interval=1.0)
        executor.stop = MagicMock()
        order = a_tracked_order("stuck", filled=Decimal("0"))
        order.order.is_open = False
        order.order.is_filled = False
        executor._order = order
        return executor

    async def test_it_waits_before_forcing(self):
        executor = self.an_executor()

        await executor.control_shutdown_process()

        self.assertEqual(executor._shutdown_ticks, 1)
        executor.stop.assert_not_called()

    async def test_it_force_stops_once_the_bound_is_reached(self):
        executor = self.an_executor()
        executor._shutdown_ticks = executor.MAX_SHUTDOWN_TICKS - 1

        await executor.control_shutdown_process()

        self.assertEqual(executor.close_type, CloseType.FAILED)
        executor.stop.assert_called_once()

    async def test_forcing_still_carries_any_known_fills(self):
        executor = self.an_executor()
        executor._partial_filled_orders = [a_tracked_order("partial", filled=Decimal("0.2"))]
        executor._shutdown_ticks = executor.MAX_SHUTDOWN_TICKS - 1

        await executor.control_shutdown_process()

        self.assertEqual(executor.close_type, CloseType.POSITION_HOLD)
        self.assertEqual(len(executor._held_position_orders), 1)


class TestEarlyStop(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        super().setUp()
        self.strategy = MagicMock()
        self.strategy.current_timestamp = 1234567890

    def test_keep_position_false_warns_because_it_cannot_unwind(self):
        """OrderExecutor does not unwind fills — that is a position executor's job — so
        asking it to is a request it cannot honour, and it says so rather than quietly
        dropping the quantity."""
        executor = OrderExecutor(self.strategy, a_config(), update_interval=1.0)

        with patch.object(OrderExecutor, "logger") as logger:
            executor.early_stop(keep_position=False)

            self.assertTrue(logger.return_value.warning.called)
