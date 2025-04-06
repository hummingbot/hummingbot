import asyncio
import time
import unittest

import pandas as pd

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.time_iterator import TimeIterator


class ClockUnitTest(unittest.TestCase):

    backtest_start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()
    backtest_end_timestamp: float = pd.Timestamp("2021-01-01 01:00:00", tz="UTC").timestamp()
    tick_size: int = 1

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    def setUp(self):
        super().setUp()
        self.realtime_start_timestamp = int(time.time())
        self.realtime_end_timestamp = self.realtime_start_timestamp + 2.0  #
        self.clock_realtime = Clock(ClockMode.REALTIME, self.tick_size, self.realtime_start_timestamp, self.realtime_end_timestamp)
        self.clock_backtest = Clock(ClockMode.BACKTEST, self.tick_size, self.backtest_start_timestamp, self.backtest_end_timestamp)

    def test_clock_mode(self):
        self.assertEqual(ClockMode.REALTIME, self.clock_realtime.clock_mode)
        self.assertEqual(ClockMode.BACKTEST, self.clock_backtest.clock_mode)

    def test_start_time(self):
        self.assertEqual(self.realtime_start_timestamp, self.clock_realtime.start_time)
        self.assertEqual(self.backtest_start_timestamp, self.clock_backtest.start_time)

    def test_tick_time(self):
        self.assertEqual(self.tick_size, self.clock_realtime.tick_size)
        self.assertEqual(self.tick_size, self.clock_backtest.tick_size)

    def test_child_iterators(self):
        # Tests child_iterators property after initialization. See also test_add_iterator
        self.assertEqual(0, len(self.clock_realtime.child_iterators))
        self.assertEqual(0, len(self.clock_backtest.child_iterators))

    def test_current_timestamp(self):
        self.assertEqual(self.backtest_start_timestamp, self.clock_backtest.current_timestamp)
        self.assertAlmostEqual((self.realtime_start_timestamp // self.tick_size) * self.tick_size, self.clock_realtime.current_timestamp)

        self.clock_backtest.backtest()
        self.clock_realtime.backtest()

        self.assertEqual(self.backtest_end_timestamp, self.clock_backtest.current_timestamp)
        self.assertLessEqual(self.realtime_end_timestamp, self.clock_realtime.current_timestamp)

    def test_add_iterator(self):
        self.assertEqual(0, len(self.clock_realtime.child_iterators))
        self.assertEqual(0, len(self.clock_backtest.child_iterators))

        time_iterator: TimeIterator = TimeIterator()
        self.clock_realtime.add_iterator(time_iterator)
        self.clock_backtest.add_iterator(time_iterator)

        self.assertEqual(1, len(self.clock_realtime.child_iterators))
        self.assertEqual(time_iterator, self.clock_realtime.child_iterators[0])
        self.assertEqual(1, len(self.clock_backtest.child_iterators))
        self.assertEqual(time_iterator, self.clock_backtest.child_iterators[0])

    def test_remove_iterator(self):
        self.assertEqual(0, len(self.clock_realtime.child_iterators))
        self.assertEqual(0, len(self.clock_backtest.child_iterators))

        time_iterator: TimeIterator = TimeIterator()
        self.clock_realtime.add_iterator(time_iterator)
        self.clock_backtest.add_iterator(time_iterator)

        self.assertEqual(1, len(self.clock_realtime.child_iterators))
        self.assertEqual(time_iterator, self.clock_realtime.child_iterators[0])
        self.assertEqual(1, len(self.clock_backtest.child_iterators))
        self.assertEqual(time_iterator, self.clock_backtest.child_iterators[0])

        self.clock_realtime.remove_iterator(time_iterator)
        self.clock_backtest.remove_iterator(time_iterator)

        self.assertEqual(0, len(self.clock_realtime.child_iterators))
        self.assertEqual(0, len(self.clock_backtest.child_iterators))

    def test_run(self):
        # Note: Technically you do not execute `run()` when in BACKTEST mode

        # Tests EnvironmentError raised when not runnning within a context
        with self.assertRaises(EnvironmentError):
            self.ev_loop.run_until_complete(self.clock_realtime.run())

        # Note: run() will essentially run indefinitely hence the enforced timeout.
        with self.assertRaises(asyncio.TimeoutError), self.clock_realtime:
            self.ev_loop.run_until_complete(asyncio.wait_for(self.clock_realtime.run(), 1))

        self.assertLess(self.realtime_start_timestamp, self.clock_realtime.current_timestamp)

    def test_run_til(self):
        # Note: Technically you do not execute `run_til()` when in BACKTEST mode

        # Tests EnvironmentError raised when not runnning within a context
        with self.assertRaises(EnvironmentError):
            self.ev_loop.run_until_complete(self.clock_realtime.run_til(self.realtime_end_timestamp))

        with self.clock_realtime:
            self.ev_loop.run_until_complete(self.clock_realtime.run_til(self.realtime_end_timestamp))

        self.assertGreaterEqual(self.clock_realtime.current_timestamp, self.realtime_end_timestamp)

    def test_backtest(self):
        # Note: Technically you do not execute `backtest()` when in REALTIME mode

        self.clock_backtest.backtest()
        self.assertGreaterEqual(self.clock_backtest.current_timestamp, self.backtest_end_timestamp)

    def test_backtest_til(self):
        # Note: Technically you do not execute `backtest_til()` when in REALTIME mode

        self.clock_backtest.backtest_til(self.backtest_start_timestamp + self.tick_size)
        self.assertGreater(self.clock_backtest.current_timestamp, self.clock_backtest.start_time)
        self.assertLess(self.clock_backtest.current_timestamp, self.backtest_end_timestamp)
