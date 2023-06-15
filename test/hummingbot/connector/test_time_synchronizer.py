import asyncio
import unittest
from typing import Awaitable
from unittest.mock import patch

import numpy.ma

from hummingbot.connector.time_synchronizer import TimeSynchronizer


class TimeSynchronizerTest(unittest.TestCase):
    def setUp(self):
        self.time_synchronizer = TimeSynchronizer()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    async def configurable_timestamp_provider(timestamp: float) -> float:
        return timestamp

    @patch("time.time")
    @patch("time.monotonic_ns")
    def test__init(self, mock_time_ns, mock_time):
        mock_time.return_value = 100.0
        mock_time_ns.return_value = 5

        # Initialize time synchronizer with time.time and time.monotonic_ns mocked
        self.time_synchronizer = TimeSynchronizer()
        self.assertEqual(100.0, self.time_synchronizer._time_reference_s)
        self.assertEqual(5, self.time_synchronizer._counter_reference_ns)

    @patch("time.time")
    def test__time_method(self, mock_time):
        mock_time.return_value = 100.0

        # _time() calls time.time()
        self.assertEqual(100.0, self.time_synchronizer._time())

    @patch("time.time")
    @patch("time.monotonic_ns")
    def test__elapsed_precise_ns_method(self, mock_monotonic_ns, mock_time):
        # Mock initial time and monotonic time when the instance was created
        mock_time.return_value = 100
        mock_monotonic_ns.side_effect = [1234567890, 1234567890 + 1234]
        self.time_synchronizer = TimeSynchronizer()  # Create new instance with mock time and monotonic time
        self.assertEqual(100.0, self.time_synchronizer._time_reference_s)
        self.assertEqual(1234567890, self.time_synchronizer._counter_reference_ns)

        # _elapsed_precise_ns() returns elapsed seconds since the instance was created (first call to monotonic_ns)
        self.assertEqual(1234, self.time_synchronizer._elapsed_precise_ns())

    @patch("time.time")
    @patch("time.monotonic_ns")
    def test__current_precise_time_ns_method(self, mock_monotonic_ns, mock_time):
        # Mock initial time and monotonic time when the instance was created
        mock_time.return_value = 12345.0
        mock_monotonic_ns.side_effect = [1234567890, 1234567890 + 1234, 1234567890 + 1234]
        self.time_synchronizer = TimeSynchronizer()  # Create new instance with mock time and monotonic time
        self.assertEqual(12345.0, self.time_synchronizer._time_reference_s)
        self.assertEqual(1234567890, self.time_synchronizer._counter_reference_ns)
        elapsed_precise_ns = self.time_synchronizer._elapsed_precise_ns()
        self.assertEqual(1234, elapsed_precise_ns)

        expected_precise_time_ns = self.time_synchronizer._time_reference_s * 1e9 + elapsed_precise_ns
        self.assertEqual(expected_precise_time_ns, self.time_synchronizer._current_precise_time_ns())

    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_precise_time_s")
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._time")
    def test__time_offset_ms_method_initialized(self, mock_time, mock_current_precise_time_s):
        # Mock initial time and monotonic time when the instance was created
        mock_time.return_value = 12345.0
        mock_current_precise_time_s.return_value = 123
        self.time_synchronizer = TimeSynchronizer()  # Create new instance with mock time and monotonic time

        self.assertFalse(self.time_synchronizer._time_offset_ms)
        self.assertEqual((12345.0 - 123) * 1e3, self.time_synchronizer.time_offset_ms)

    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_precise_time_s")
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._time")
    def test__time_offset_ms_method_with_queue(self, mock_time, mock_current_precise_time_s):
        # Mock initial time and monotonic time when the instance was created
        mock_time.return_value = 12345.0
        mock_current_precise_time_s.return_value = 123
        self.time_synchronizer = TimeSynchronizer()  # Create new instance with mock time and monotonic time
        self.assertFalse(self.time_synchronizer._time_offset_ms)

        self.time_synchronizer._time_offset_ms.append(2)
        self.time_synchronizer._time_offset_ms.append(3)
        self.time_synchronizer._time_offset_ms.append(4)

        median = numpy.median(self.time_synchronizer._time_offset_ms)
        weighted_average = numpy.average(self.time_synchronizer._time_offset_ms,
                                         weights=range(1, len(self.time_synchronizer._time_offset_ms) * 2 + 1, 2))
        expected_offset = (median + weighted_average) / 2
        self.assertEqual(expected_offset, self.time_synchronizer.time_offset_ms)

    def test_add_clear_time_offset_ms_sample_methods(self):
        self.time_synchronizer.add_time_offset_ms_sample(100.0)
        self.time_synchronizer.add_time_offset_ms_sample(200.0)
        self.assertEqual(len(self.time_synchronizer._time_offset_ms), 2)
        self.time_synchronizer.clear_time_offset_ms_samples()
        self.assertEqual(len(self.time_synchronizer._time_offset_ms), 0)

    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_precise_time_ns")
    def test_update_server_time_offset_with_time_provider_method(self, mock_current_precise_time_ns):
        async def async_test():
            first_time: float = 100 * 1e9
            second_time: float = 101 * 1e9 + 1234
            mock_current_precise_time_ns.side_effect = [first_time, second_time]
            average_local_time_ms = (first_time + second_time) * 1e-6 / 2

            time_provider_ms = asyncio.Future()
            server_time_ms = 101 * 1e3
            time_provider_ms.set_result(server_time_ms)
            await self.time_synchronizer.update_server_time_offset_with_time_provider(time_provider_ms)
            self.assertEqual(len(self.time_synchronizer._time_offset_ms), 1)
            self.assertEqual(server_time_ms - average_local_time_ms, self.time_synchronizer._time_offset_ms[0])
        asyncio.run(async_test())

    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_precise_time_ns")
    def test_update_server_time_offset_with_time_provider_method_raises_on_seconds(self, mock_current_precise_time_ns):
        async def async_test():
            first_time: float = 100 * 1e9
            second_time: float = 101 * 1e9 + 1234
            mock_current_precise_time_ns.side_effect = [first_time, second_time]

            time_provider_ms = asyncio.Future()
            # Set server time in seconds instead of milliseconds, well 2 orders of mag from milliseconds
            server_time_ms = 101 * 0.9e1
            time_provider_ms.set_result(server_time_ms)
            with self.assertRaises(ValueError):
                await self.time_synchronizer.update_server_time_offset_with_time_provider(time_provider_ms)
        asyncio.run(async_test())

    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_precise_time_ns")
    def test_update_server_time_offset_with_time_provider_method_raises_on_useconds(self, mock_current_precise_time_ns):
        async def async_test():
            first_time: float = 100 * 1e9
            second_time: float = 101 * 1e9 + 1234
            mock_current_precise_time_ns.side_effect = [first_time, second_time]

            time_provider_ms = asyncio.Future()
            # Set server time in seconds instead of milliseconds, well 2 orders of mag from milliseconds
            server_time_ms = 101 * 1.1e5
            time_provider_ms.set_result(server_time_ms)
            with self.assertRaises(ValueError):
                await self.time_synchronizer.update_server_time_offset_with_time_provider(time_provider_ms)
        asyncio.run(async_test())

    @patch("time.time")
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_precise_time_ns")
    def test_update_server_time_if_not_initialized_method(self, mock_monotonic_ns, mock_time):
        async def async_test():
            mock_monotonic_ns.return_value = 1000000000
            mock_time.return_value = 100.0
            time_provider_ms = asyncio.Future()
            time_provider_ms.set_result(500)
            await self.time_synchronizer.update_server_time_if_not_initialized(time_provider_ms)
            self.assertEqual(len(self.time_synchronizer._time_offset_ms), 1)
            time_provider_ms = asyncio.Future()
            time_provider_ms.set_result(600)
            await self.time_synchronizer.update_server_time_if_not_initialized(time_provider_ms)
            self.assertEqual(len(self.time_synchronizer._time_offset_ms), 1)
        asyncio.run(async_test())

    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_precise_time_s")
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_precise_time_ns")
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._time")
    def test_time_without_registered_offsets_returns_local_time(self, time_mock, seconds_counter_mock,
                                                                seconds_time_mock):
        now = 1640000000.0
        time_mock.return_value = now  # Return now directly
        seconds_time_mock.return_value = now  # Return now directly
        seconds_counter_mock.side_effect = [2e9, 3e9]
        time_provider = TimeSynchronizer()

        synchronized_time = time_provider.time()
        self.assertEqual(now, synchronized_time)

    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_precise_time_s")
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_precise_time_ns")
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._time")
    def test_time_with_one_registered_offset(self, time_mock, seconds_counter_mock, local_precise_time):
        # At t0, local time is 1640000000.0, server time is 1640000020.0
        local_time = 1640000000.0
        server_time = local_time + 20.0
        # When querying the server time, our precise local time is after 0s
        first_precise_time_delay = 0
        # When querying the server time, our round-trip local time is after 30s
        second_precise_time_delay = 30
        # We request the synchronized time after 50s
        local_time_for_sync_time_check_delay = 50

        time_mock.return_value = local_time
        seconds_counter_mock.side_effect = [(local_time + first_precise_time_delay) * 1e9,
                                            (local_time + second_precise_time_delay) * 1e9]
        local_precise_time.side_effect = [local_time + local_time_for_sync_time_check_delay]

        time_provider = TimeSynchronizer()
        self.async_run_with_timeout(
            time_provider.update_server_time_offset_with_time_provider(
                time_provider=self.configurable_timestamp_provider(server_time * 1e3)
            ))
        self.assertEqual(len(time_provider._time_offset_ms), 1)
        # The effective local precise time is the mean of the two precise times
        average_precise_time = local_time + (first_precise_time_delay + second_precise_time_delay) / 2
        calculated_offset_ms = (server_time - average_precise_time) * 1e3
        self.assertEqual(calculated_offset_ms, time_provider._time_offset_ms[0])

        synchronized_time = time_provider.time()
        self.assertEqual(
            local_time + local_time_for_sync_time_check_delay + calculated_offset_ms / 1e3,
            synchronized_time)

    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_precise_time_s")
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_precise_time_ns")
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._time")
    def test_time_with_several_registered_offset(self, time_mock, seconds_counter_mock, local_precise_time):
        # At t0, local time is 1640000000.0, server time is 1640000020.0
        local_time = 1640000000.0
        server_time = [local_time + 0, local_time + 17, local_time + 27]
        # When querying the server time, our precise local time is after 0s
        ptd = [
            (local_time + 0) * 1e9,
            (local_time + 13) * 1e9,
            (local_time + 17) * 1e9,
            (local_time + 22) * 1e9,
            (local_time + 27) * 1e9,
            (local_time + 30) * 1e9,
        ]
        # We request the synchronized time after 50s
        local_time_for_sync_time_check = local_time + 50

        time_mock.return_value = local_time
        seconds_counter_mock.side_effect = ptd
        local_precise_time.side_effect = [local_time_for_sync_time_check]

        time_provider = TimeSynchronizer()
        for i in range(int(len(ptd) / 2)):
            self.async_run_with_timeout(
                time_provider.update_server_time_offset_with_time_provider(
                    time_provider=self.configurable_timestamp_provider(server_time[i] * 1e3)
                ))
            average_precise_time = (ptd[2 * i] + ptd[2 * i + 1]) / 2
            calculated_offset_ms = (server_time[i] - average_precise_time / 1e9) * 1e3
            self.assertEqual(calculated_offset_ms, time_provider._time_offset_ms[i])

        self.assertEqual(len(time_provider._time_offset_ms), 3)
        calculated_median = numpy.median(time_provider._time_offset_ms)
        calculated_weighted_average = numpy.average(
            time_provider._time_offset_ms,
            weights=range(1, len(time_provider._time_offset_ms) * 2 + 1, 2))
        calculated_offset = numpy.mean([calculated_median, calculated_weighted_average])

        synchronized_time = time_provider.time()
        self.assertEqual(
            local_time_for_sync_time_check + calculated_offset * 1e-3,
            synchronized_time)
