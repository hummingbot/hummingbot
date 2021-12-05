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
        self.assertEqual(len(self.debug_logs), 1)
        self.assertEqual(self.debug_logs[0], "Time span execution: tick will not be processed "
                                             f"(executing between {start_timestamp} and {end_timestamp})")

        state.process_tick(datetime.fromisoformat("2021-06-22 09:00:00").timestamp(), strategy)
        strategy.process_tick.assert_called()

        state.process_tick(datetime.fromisoformat("2021-06-22 09:00:00").timestamp(), strategy)
        strategy.process_tick.assert_called()

        strategy.process_tick.reset_mock()
        state.process_tick(datetime.fromisoformat("2021-06-22 10:00:01").timestamp(), strategy)
        strategy.process_tick.assert_not_called()
        self.assertEqual(len(self.debug_logs), 2)
        self.assertEqual(self.debug_logs[1], "Time span execution: tick will not be processed "
                                             f"(executing between {start_timestamp} and {end_timestamp})")

        state = RunInTimeConditionalExecutionState(start_timestamp=start_timestamp.time(), end_timestamp=end_timestamp.time())

        state.process_tick(datetime.fromisoformat("2021-06-22 08:59:59").timestamp(), strategy)
        strategy.process_tick.assert_not_called()
        self.assertEqual(len(self.debug_logs), 3)
        self.assertEqual(self.debug_logs[0], "Time span execution: tick will not be processed "
                                             f"(executing between {start_timestamp} and {end_timestamp})")

        state.process_tick(datetime.fromisoformat("2021-06-22 09:00:00").timestamp(), strategy)
        strategy.process_tick.assert_called()

        state.process_tick(datetime.fromisoformat("2021-06-22 09:00:00").timestamp(), strategy)
        strategy.process_tick.assert_called()

        strategy.process_tick.reset_mock()
        state.process_tick(datetime.fromisoformat("2021-06-22 10:00:01").timestamp(), strategy)
        strategy.process_tick.assert_not_called()
        self.assertEqual(len(self.debug_logs), 4)
        self.assertEqual(self.debug_logs[1], "Time span execution: tick will not be processed "
                                             f"(executing between {start_timestamp} and {end_timestamp})")

        state.process_tick(datetime.fromisoformat("2021-06-30 08:59:59").timestamp(), strategy)
        strategy.process_tick.assert_not_called()
        self.assertEqual(len(self.debug_logs), 5)
        self.assertEqual(self.debug_logs[0], "Time span execution: tick will not be processed "
                                             f"(executing between {start_timestamp} and {end_timestamp})")

        state.process_tick(datetime.fromisoformat("2021-06-30 09:00:00").timestamp(), strategy)
        strategy.process_tick.assert_called()

        state.process_tick(datetime.fromisoformat("2021-06-30 09:00:00").timestamp(), strategy)
        strategy.process_tick.assert_called()

        strategy.process_tick.reset_mock()
        state.process_tick(datetime.fromisoformat("2021-06-30 10:00:01").timestamp(), strategy)
        strategy.process_tick.assert_not_called()
        self.assertEqual(len(self.debug_logs), 6)
        self.assertEqual(self.debug_logs[1], "Time span execution: tick will not be processed "
                                             f"(executing between {start_timestamp} and {end_timestamp})")
