from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.strategy.conditional_execution_state import RunAlwaysExecutionState, RunInTimeConditionalExecutionState


class RunAlwaysExecutionStateTests(TestCase):

    def test_always_process_tick(self):
        strategy = MagicMock()
        state = RunAlwaysExecutionState()
        timestamp = datetime.now
        state.process_tick(timestamp, strategy)

        strategy.process_tick.assert_called_with(timestamp, True)


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

        timestamp = datetime.fromisoformat("2021-06-22 08:59:59").timestamp()
        state.process_tick(timestamp, strategy)
        strategy.process_tick.assert_called_with(timestamp, False)
        self.assertEqual(len(self.debug_logs), 1)
        self.assertEqual(self.debug_logs[0], "Time span execution: tick will not be processed "
                                             f"(executing between {start_timestamp} and {end_timestamp})")

        timestamp = datetime.fromisoformat("2021-06-22 09:00:00").timestamp()
        state.process_tick(timestamp, strategy)
        strategy.process_tick.assert_called_with(timestamp, True)

        timestamp = datetime.fromisoformat("2021-06-22 09:00:00").timestamp()
        state.process_tick(timestamp, strategy)
        strategy.process_tick.assert_called_with(timestamp, True)

        strategy.process_tick.reset_mock()
        timestamp = datetime.fromisoformat("2021-06-22 10:00:01").timestamp()
        state.process_tick(timestamp, strategy)
        strategy.process_tick.assert_called_with(timestamp, False)
        self.assertEqual(len(self.debug_logs), 2)
        self.assertEqual(self.debug_logs[1], "Time span execution: tick will not be processed "
                                             f"(executing between {start_timestamp} and {end_timestamp})")

        state = RunInTimeConditionalExecutionState(start_timestamp=start_timestamp.time(), end_timestamp=end_timestamp.time())

        timestamp = datetime.fromisoformat("2021-06-22 08:59:59").timestamp()
        state.process_tick(timestamp, strategy)
        strategy.process_tick.assert_called_with(timestamp, False)
        self.assertEqual(len(self.debug_logs), 3)
        self.assertEqual(self.debug_logs[0], "Time span execution: tick will not be processed "
                                             f"(executing between {start_timestamp} and {end_timestamp})")

        timestamp = datetime.fromisoformat("2021-06-22 09:00:00").timestamp()
        state.process_tick(timestamp, strategy)
        strategy.process_tick.assert_called_with(timestamp, True)

        timestamp = datetime.fromisoformat("2021-06-22 09:00:00").timestamp()
        state.process_tick(timestamp, strategy)
        strategy.process_tick.assert_called_with(timestamp, True)

        strategy.process_tick.reset_mock()
        timestamp = datetime.fromisoformat("2021-06-22 10:00:01").timestamp()
        state.process_tick(timestamp, strategy)
        strategy.process_tick.assert_called_with(timestamp, False)
        self.assertEqual(len(self.debug_logs), 4)
        self.assertEqual(self.debug_logs[1], "Time span execution: tick will not be processed "
                                             f"(executing between {start_timestamp} and {end_timestamp})")

        timestamp = datetime.fromisoformat("2021-06-30 08:59:59").timestamp()
        state.process_tick(timestamp, strategy)
        strategy.process_tick.assert_called_with(timestamp, False)
        self.assertEqual(len(self.debug_logs), 5)
        self.assertEqual(self.debug_logs[0], "Time span execution: tick will not be processed "
                                             f"(executing between {start_timestamp} and {end_timestamp})")

        timestamp = datetime.fromisoformat("2021-06-30 09:00:00").timestamp()
        state.process_tick(timestamp, strategy)
        strategy.process_tick.assert_called_with(timestamp, True)

        timestamp = datetime.fromisoformat("2021-06-30 09:00:00").timestamp()
        state.process_tick(timestamp, strategy)
        strategy.process_tick.assert_called_with(timestamp, True)

        strategy.process_tick.reset_mock()
        timestamp = datetime.fromisoformat("2021-06-30 10:00:01").timestamp()
        state.process_tick(timestamp, strategy)
        strategy.process_tick.assert_called_with(timestamp, False)
        self.assertEqual(len(self.debug_logs), 6)
        self.assertEqual(self.debug_logs[1], "Time span execution: tick will not be processed "
                                             f"(executing between {start_timestamp} and {end_timestamp})")
