import unittest
import math
import pandas as pd

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.py_time_iterator import PyTimeIterator

NaN = float("nan")


class MockPyTimeIterator(PyTimeIterator):

    def __init__(self):
        super().__init__()
        self._mock_variable = None

    @property
    def mock_variable(self):
        return self._mock_variable

    def tick(self, timestamp: float):
        self._mock_variable = timestamp


class PyTimeIteratorUnitTest(unittest.TestCase):

    start_timestamp: float = pd.Timestamp("2021-01-01", tz="UTC").timestamp()
    end_timestamp: float = pd.Timestamp("2022-01-01 01:00:00", tz="UTC").timestamp()
    tick_size: int = 10

    def setUp(self):
        self.py_time_iterator = MockPyTimeIterator()
        self.clock = Clock(ClockMode.BACKTEST, self.tick_size, self.start_timestamp, self.end_timestamp)
        self.clock.add_iterator(self.py_time_iterator)

    def test_current_timestamp(self):
        # On initialization, current_timestamp should be NaN
        self.assertTrue(math.isnan(self.py_time_iterator.current_timestamp))

        self.py_time_iterator.start(self.clock)
        self.clock.backtest_til(self.start_timestamp)
        self.assertEqual(self.start_timestamp, self.py_time_iterator.current_timestamp)

    def test_clock(self):
        # On initialization, clock should be None
        self.assertTrue(self.py_time_iterator.clock is None)

        self.py_time_iterator.start(self.clock)
        self.assertEqual(self.clock, self.py_time_iterator.clock)

    def test_start(self):
        self.py_time_iterator.start(self.clock)
        self.assertEqual(self.clock, self.py_time_iterator.clock)
        self.assertEqual(self.start_timestamp, self.py_time_iterator.current_timestamp)

    def test_stop(self):
        self.py_time_iterator.start(self.clock)
        self.assertEqual(self.clock, self.py_time_iterator.clock)
        self.assertEqual(self.start_timestamp, self.py_time_iterator.current_timestamp)

        self.py_time_iterator.stop(self.clock)
        self.assertTrue(math.isnan(self.py_time_iterator.current_timestamp))
        self.assertTrue(self.py_time_iterator.clock is None)

    def test_tick(self):
        self.py_time_iterator.start(self.clock)
        self.assertEqual(self.start_timestamp, self.py_time_iterator.current_timestamp)

        # c_tick is called within Clock
        self.clock.backtest_til(self.start_timestamp + self.tick_size)
        self.assertEqual(self.start_timestamp + self.tick_size, self.py_time_iterator.current_timestamp)

        self.assertEqual(self.start_timestamp + self.tick_size, self.py_time_iterator.mock_variable)
