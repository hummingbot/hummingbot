import unittest
import asyncio
import pandas as pd

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.network_iterator import (
    NetworkIterator,
    NetworkStatus,
)


class MockNetworkIterator(NetworkIterator):

    def __init__(self):
        super().__init__()
        self._start_network_event = asyncio.Event()
        self._stop_network_event = asyncio.Event()

    async def start_network(self):
        self._start_network_event.set()
        self._stop_network_event = asyncio.Event()

    async def stop_network(self):
        self._stop_network_event.set()

        self._network_status = NetworkStatus.STOPPED
        self._start_network_event = asyncio.Event()

    async def check_network(self):
        if self.network_status != NetworkStatus.CONNECTED:
            self.last_connected_timestamp = self.current_timestamp
            return NetworkStatus.CONNECTED
        else:
            return NetworkStatus.NOT_CONNECTED


class NetworkIteratorUnitTest(unittest.TestCase):

    start: pd.Timestamp = pd.Timestamp("2021-01-01", tz="UTC")
    end: pd.Timestamp = pd.Timestamp("2022-01-01 01:00:00", tz="UTC")
    start_timestamp: float = start.timestamp()
    end_timestamp: float = end.timestamp()
    clock_tick_size = 10

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        return super().setUpClass()

    def setUp(self):
        self.network_iterator = MockNetworkIterator()
        self.clock: Clock = Clock(ClockMode.BACKTEST, self.clock_tick_size, self.start_timestamp, self.end_timestamp)
        self.clock.add_iterator(self.network_iterator)
        return super().setUp()

    def test_network_status(self):
        # This test technically tests the _check_network_loop() and all its paths.
        self.assertEqual(NetworkStatus.STOPPED, self.network_iterator.network_status)

        self.network_iterator.check_network_interval = 0.5

        self.clock.backtest_til(self.start_timestamp)
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        self.assertEqual(NetworkStatus.CONNECTED, self.network_iterator.network_status)
        self.assertTrue(self.network_iterator._start_network_event.is_set())

        self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        self.assertEqual(NetworkStatus.NOT_CONNECTED, self.network_iterator.network_status)
        self.assertTrue(self.network_iterator._stop_network_event.is_set())

    def test_last_connected_timestamp(self):
        self.clock.backtest_til(self.start_timestamp)
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        self.assertEqual(self.start_timestamp, self.network_iterator.last_connected_timestamp)

    def test_check_network_task(self):
        self.clock.backtest_til(self.start_timestamp)
        self.assertIsNotNone(self.network_iterator.check_network_task)

    def test_check_network_interval(self):
        # Default interval
        self.assertEqual(10.0, self.network_iterator.check_network_interval)

    def test_network_error_wait_time(self):
        # Default wait time
        self.assertEqual(60.0, self.network_iterator.network_error_wait_time)

    def test_check_network_timeout(self):
        # Default timeout
        self.assertEqual(5.0, self.network_iterator.check_network_timeout)

    def test_start_network(self):
        self.assertFalse(self.network_iterator._start_network_event.is_set())
        self.assertFalse(self.network_iterator._stop_network_event.is_set())

        self.ev_loop.run_until_complete(self.network_iterator.start_network())
        self.assertTrue(self.network_iterator._start_network_event.is_set())
        self.assertFalse(self.network_iterator._stop_network_event.is_set())

    def test_stop_network(self):
        self.assertFalse(self.network_iterator._start_network_event.is_set())
        self.assertFalse(self.network_iterator._stop_network_event.is_set())

        self.ev_loop.run_until_complete(self.network_iterator.stop_network())
        self.assertFalse(self.network_iterator._start_network_event.is_set())
        self.assertTrue(self.network_iterator._stop_network_event.is_set())
        self.assertEqual(NetworkStatus.STOPPED, self.network_iterator.network_status)

    def test_start(self):
        self.assertEqual(NetworkStatus.STOPPED, self.network_iterator.network_status)

        self.network_iterator.start(self.clock, self.clock.current_timestamp)

        self.assertIsNotNone(self.network_iterator.check_network_task)
        self.assertEqual(NetworkStatus.NOT_CONNECTED, self.network_iterator.network_status)

    def test_stop(self):
        self.assertEqual(NetworkStatus.STOPPED, self.network_iterator.network_status)

        self.network_iterator.start(self.clock, self.clock.current_timestamp)
        self.assertEqual(NetworkStatus.NOT_CONNECTED, self.network_iterator.network_status)

        self.network_iterator.stop(self.clock)

        self.assertEqual(NetworkStatus.STOPPED, self.network_iterator.network_status)
        self.assertIsNone(self.network_iterator.check_network_task)
