import unittest
import math
import pandas as pd

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.time_iterator import TimeIterator

NaN = float("nan")


class TimeIteratorUnitTest(unittest.TestCase):

    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()
    end_timestamp: float = pd.Timestamp("2022-01-01 01:00:00", tz="UTC").timestamp()
    tick_size: int = 10

    def setUp(self):
        self.time_iterator = TimeIterator()
        self.clock = Clock(ClockMode.BACKTEST, self.tick_size, self.start_timestamp, self.end_timestamp)
        self.clock.add_iterator(self.time_iterator)

    def test_current_timestamp(self):
        # On initialization, current_timestamp should be NaN
        self.assertTrue(math.isnan(self.time_iterator.current_timestamp))

        self.time_iterator.start(self.clock)
        self.clock.backtest_til(self.start_timestamp)
        self.assertEqual(self.start_timestamp, self.time_iterator.current_timestamp)

    def test_clock(self):
        # On initialization, clock should be None
        self.assertTrue(self.time_iterator.clock is None)

        self.time_iterator.start(self.clock)
        self.assertEqual(self.clock, self.time_iterator.clock)

    def test_start(self):
        self.time_iterator.start(self.clock)
        self.assertEqual(self.clock, self.time_iterator.clock)
        self.assertEqual(self.start_timestamp, self.time_iterator.current_timestamp)

    def test_stop(self):
        self.time_iterator.start(self.clock)
        self.assertEqual(self.clock, self.time_iterator.clock)
        self.assertEqual(self.start_timestamp, self.time_iterator.current_timestamp)

        self.time_iterator.stop(self.clock)
        self.assertTrue(math.isnan(self.time_iterator.current_timestamp))
        self.assertTrue(self.time_iterator.clock is None)

    def test_tick(self):
        self.time_iterator.start(self.clock)
        self.assertEqual(self.start_timestamp, self.time_iterator.current_timestamp)

        # c_tick is called within Clock
        self.clock.backtest_til(self.start_timestamp + self.tick_size)
        self.assertEqual(self.start_timestamp + self.tick_size, self.time_iterator.current_timestamp)
