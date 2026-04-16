from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.strategy.conditional_execution_state import RunAlwaysExecutionState, RunInTimeConditionalExecutionState


class RunAlwaysExecutionStateTests(TestCase):
    def test_always_process_tick(self):
        strategy = MagicMock()
        state = RunAlwaysExecutionState()
        state.process_tick(datetime.now, strategy)

        strategy.process_tick.assert_called()
        strategy.cancel_active_orders.assert_not_called()


class RunInTimeSpanExecutionStateTests(TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.debug_logs = []

    def debug(self, message: str):
        self.debug_logs.append(message)

    def test_process_tick_when_current_time_in_span(self):
        start_timestamp = datetime.fromisoformat("2021-06-22 09:00:00")
        end_timestamp = datetime.fromisoformat("2021-06-22 10:00:00")
        state = RunInTimeConditionalExecutionState(start_timestamp=start_timestamp, end_timestamp=end_timestamp)

        strategy = MagicMock()
        strategy.logger().debug.side_effect = self.debug

        state.process_tick(datetime.fromisoformat("2021-06-22 08:59:59").timestamp(), strategy)
        strategy.process_tick.assert_not_called()
        strategy.cancel_active_orders.assert_called()
        self.assertEqual(len(self.debug_logs), 1)
        self.assertEqual(
            self.debug_logs[0],
            "Time span execution: tick will not be processed "
            f"(executing between {start_timestamp} and {end_timestamp})",
        )

        state.process_tick(datetime.fromisoformat("2021-06-22 09:00:00").timestamp(), strategy)
        strategy.process_tick.assert_called()

        state.process_tick(datetime.fromisoformat("2021-06-22 09:00:00").timestamp(), strategy)
        strategy.process_tick.assert_called()

        strategy.process_tick.reset_mock()
        state.process_tick(datetime.fromisoformat("2021-06-22 10:00:01").timestamp(), strategy)
        strategy.process_tick.assert_not_called()
        strategy.cancel_active_orders.assert_called()
        self.assertEqual(len(self.debug_logs), 2)
        self.assertEqual(
            self.debug_logs[1],
            "Time span execution: tick will not be processed "
            f"(executing between {start_timestamp} and {end_timestamp})",
        )

        state = RunInTimeConditionalExecutionState(
            start_timestamp=start_timestamp.time(), end_timestamp=end_timestamp.time()
        )

        state.process_tick(datetime.fromisoformat("2021-06-22 08:59:59").timestamp(), strategy)
        strategy.process_tick.assert_not_called()
        strategy.cancel_active_orders.assert_called()
        self.assertEqual(len(self.debug_logs), 3)
        self.assertEqual(
            self.debug_logs[0],
            "Time span execution: tick will not be processed "
            f"(executing between {start_timestamp} and {end_timestamp})",
        )

        state.process_tick(datetime.fromisoformat("2021-06-22 09:00:00").timestamp(), strategy)
        strategy.process_tick.assert_called()

        state.process_tick(datetime.fromisoformat("2021-06-22 09:00:00").timestamp(), strategy)
        strategy.process_tick.assert_called()

        strategy.process_tick.reset_mock()
        state.process_tick(datetime.fromisoformat("2021-06-22 10:00:01").timestamp(), strategy)
        strategy.process_tick.assert_not_called()
        strategy.cancel_active_orders.assert_called()
        self.assertEqual(len(self.debug_logs), 4)
        self.assertEqual(
            self.debug_logs[1],
            "Time span execution: tick will not be processed "
            f"(executing between {start_timestamp} and {end_timestamp})",
        )

        state.process_tick(datetime.fromisoformat("2021-06-30 08:59:59").timestamp(), strategy)
        strategy.process_tick.assert_not_called()
        strategy.cancel_active_orders.assert_called()
        self.assertEqual(len(self.debug_logs), 5)
        self.assertEqual(
            self.debug_logs[0],
            "Time span execution: tick will not be processed "
            f"(executing between {start_timestamp} and {end_timestamp})",
        )

        state.process_tick(datetime.fromisoformat("2021-06-30 09:00:00").timestamp(), strategy)
        strategy.process_tick.assert_called()

        state.process_tick(datetime.fromisoformat("2021-06-30 09:00:00").timestamp(), strategy)
        strategy.process_tick.assert_called()

        strategy.process_tick.reset_mock()
        state.process_tick(datetime.fromisoformat("2021-06-30 10:00:01").timestamp(), strategy)
        strategy.process_tick.assert_not_called()
        strategy.cancel_active_orders.assert_called()
        self.assertEqual(len(self.debug_logs), 6)
        self.assertEqual(
            self.debug_logs[1],
            "Time span execution: tick will not be processed "
            f"(executing between {start_timestamp} and {end_timestamp})",
        )


# ── Coverage tests for missing lines 81 and 112 ───────────────────────────────


def test_run_in_time_conditional_eq_same_values():
    """Line 81: __eq__ returns True when both timestamps match."""
    start = datetime.fromisoformat("2021-06-22 09:00:00")
    end = datetime.fromisoformat("2021-06-22 10:00:00")
    state_a = RunInTimeConditionalExecutionState(start_timestamp=start, end_timestamp=end)
    state_b = RunInTimeConditionalExecutionState(start_timestamp=start, end_timestamp=end)
    assert state_a == state_b


def test_run_in_time_conditional_eq_different_values():
    """Line 81: __eq__ returns False when timestamps differ."""
    start = datetime.fromisoformat("2021-06-22 09:00:00")
    end_a = datetime.fromisoformat("2021-06-22 10:00:00")
    end_b = datetime.fromisoformat("2021-06-22 11:00:00")
    state_a = RunInTimeConditionalExecutionState(start_timestamp=start, end_timestamp=end_a)
    state_b = RunInTimeConditionalExecutionState(start_timestamp=start, end_timestamp=end_b)
    assert state_a != state_b


def test_process_tick_delayed_start_before_time_logs_debug():
    """Line 112: delayed-start (datetime, no end) path cancels and logs when tick is before start."""
    # start in the far future so timestamp < start triggers the else branch
    future_start = datetime.fromisoformat("2099-01-01 00:00:00")
    state = RunInTimeConditionalExecutionState(start_timestamp=future_start, end_timestamp=None)

    debug_logs = []
    strategy = MagicMock()
    strategy.logger().debug.side_effect = lambda msg: debug_logs.append(msg)

    state.process_tick(datetime.fromisoformat("2021-06-22 09:00:00").timestamp(), strategy)

    strategy.process_tick.assert_not_called()
    strategy.cancel_active_orders.assert_called_once()
    assert len(debug_logs) == 1
    assert "Delayed start execution" in debug_logs[0]
