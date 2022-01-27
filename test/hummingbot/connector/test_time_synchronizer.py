import asyncio
import statistics

from typing import Awaitable
from unittest import TestCase
from unittest.mock import patch

from hummingbot.connector.time_synchronizer import TimeSynchronizer


class TimeSynchronizerTests(TestCase):

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    async def configurable_timestamp_provider(timestamp: float) -> float:
        return timestamp

    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._time")
    def test_time_with_registered_offsets_returns_local_time(self, time_mock, seconds_counter_mock):
        now = 1640000000.0
        time_mock.side_effect = [now]
        seconds_counter_mock.side_effect = [2, 3]
        time_provider = TimeSynchronizer()

        synchronized_time = time_provider.time()
        self.assertEqual(now + (2 - 3), synchronized_time)

    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._time")
    def test_time_with_one_registered_offset(self, _, seconds_counter_mock):
        now = 1640000020.0
        seconds_counter_mock.side_effect = [10, 30, 31]

        time_provider = TimeSynchronizer()
        self.async_run_with_timeout(
            time_provider.update_server_time_offset_with_time_provider(
                time_provider=self.configurable_timestamp_provider(now * 1e3)
            ))
        synchronized_time = time_provider.time()
        seconds_difference_getting_time = 30 - 10
        seconds_difference_when_calculating_current_time = 31
        self.assertEqual(
            now - seconds_difference_getting_time + seconds_difference_when_calculating_current_time,
            synchronized_time)

    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._time")
    def test_time_calculated_with_mean_of_all_offsets(self, _, seconds_counter_mock):
        first_time = 1640000003.0
        second_time = 16400000010.0
        third_time = 1640000016.0
        seconds_counter_mock.side_effect = [2, 4, 6, 10, 11, 13, 25]

        time_provider = TimeSynchronizer()
        for time in [first_time, second_time, third_time]:
            self.async_run_with_timeout(
                time_provider.update_server_time_offset_with_time_provider(
                    time_provider=self.configurable_timestamp_provider(time * 1e3)
                ))
        synchronized_time = time_provider.time()
        first_expected_offset = first_time - (4 + 2) / 2
        second_expected_offset = second_time - (10 + 6) / 2
        third_expected_offset = third_time - (13 + 11) / 2
        expected_offsets = [first_expected_offset, second_expected_offset, third_expected_offset]
        seconds_difference_when_calculating_current_time = 25
        self.assertEqual(
            statistics.median(expected_offsets) + seconds_difference_when_calculating_current_time,
            synchronized_time)
