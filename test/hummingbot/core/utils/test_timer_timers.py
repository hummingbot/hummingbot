import math
import re
import time
import unittest

from hummingbot.core.utils.timer import Timer, TimerAlreadyStartedError, TimerNotStartedError
from hummingbot.core.utils.timers import Timers

#
# Test functions
#
TIME_PREFIX = "Wasted time:"
TIME_MESSAGE = f"{TIME_PREFIX} {{:.4f}} seconds"
RE_TIME_MESSAGE = re.compile(TIME_PREFIX + r" 0\.\d{4} seconds")


def waste_time(num=1000):
    """Just waste a little bit of time"""
    sum(n ** 2 for n in range(num))


@Timer(text=TIME_MESSAGE)
def decorated_timewaste(num=1000):
    """Just waste a little bit of time"""
    sum(n ** 2 for n in range(num))


@Timer(name="accumulator", text=TIME_MESSAGE)
def accumulated_timewaste(num=1000):
    """Just waste a little bit of time"""
    sum(n ** 2 for n in range(num))


class TestTimer(unittest.TestCase):
    level = 0

    def setUp(self):
        super().setUp()
        self.timer = Timer()
        self.log_records = []
        self.timer.logger().setLevel(1)
        self.timer.logger().addHandler(self)

    def handle(self, record):
        self.log_records.append(record)

    def is_partially_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and message in record.getMessage() for
            record in self.log_records)

    def test_error_if_timer_not_running(self):
        """Test that timer raises error if it is stopped before started"""
        t = Timer(text=TIME_MESSAGE)
        with self.assertRaises(TimerNotStartedError):
            t.stop()

    def test_error_if_restarting_running_timer(self):
        """Test that restarting a running timer raises an error"""
        t = Timer(text=TIME_MESSAGE)
        t.start()
        with self.assertRaises(TimerAlreadyStartedError):
            t.start()

    def test_last_starts_as_nan(self):
        """Test that .last attribute is initialized as nan"""
        t = Timer()
        self.assertTrue(math.isnan(t.last))

    def test_timer_sets_last(self):
        """Test that .last attribute is properly set"""
        with Timer() as t:
            time.sleep(0.02)

        self.assertTrue(t.last >= 0.02)

    def test_timers_cleared(self):
        """Test that timers can be cleared"""
        with Timer(name="timer_to_be_cleared"):
            waste_time()

        self.assertTrue("timer_to_be_cleared" in Timer.timers)
        Timer.timers.clear()
        self.assertTrue(not Timer.timers)

    def test_running_cleared_timers(self):
        """Test that timers can still be run after they're cleared"""
        t = Timer(name="timer_to_be_cleared")
        Timer.timers.clear()

        accumulated_timewaste()
        with t:
            waste_time()

        self.assertTrue("accumulator" in Timer.timers)
        self.assertTrue("timer_to_be_cleared" in Timer.timers)

    def test_timers_stats(self):
        """Test that we can get basic statistics from timers"""
        name = "timer_with_stats"
        t = Timer(name=name)
        for num in range(5, 10):
            with t:
                waste_time(num=100 * num)

        stats = Timer.timers
        self.assertTrue(stats.total(name) == stats[name])
        self.assertTrue(stats.count(name) == 5)
        self.assertTrue(stats.min(name) <= stats.median(name) <= stats.max(name))
        self.assertTrue(stats.mean(name) >= stats.min(name))
        self.assertTrue(stats.stdev(name) >= 0)

    def test_stats_missing_timers(self):
        """Test that getting statistics from non-existent timers raises exception"""
        with self.assertRaises(KeyError):
            Timer.timers.count("non_existent_timer")

        with self.assertRaises(KeyError):
            Timer.timers.stdev("non_existent_timer")

    def test_setting_timers_exception(self):
        """Test that setting .timers items raises exception"""
        with self.assertRaises(TypeError):
            Timer.timers["set_timer"] = 1.23

    def test_timer_context_manager(self):
        """Test Timer functionality as a context manager"""
        start = time.time()
        with Timer() as t:
            waste_time()
        elapsed = time.time() - start
        self.assertTrue(t.last >= elapsed)

    def test_timer_split_methods(self):
        """Test split_in_ns and split_in_s methods"""
        t = Timer()
        t.start()
        time.sleep(0.02)
        split_ns = t.split_in_ns()
        split_s = t.split_in_s()
        self.assertTrue(split_ns >= 20000000)  # 0.02 seconds is 20000000 nanoseconds
        self.assertTrue(split_s >= 0.02)

    def test_timer_has_elapsed(self):
        """Test has_elapsed_in_s method"""
        t = Timer()
        t.start()
        time.sleep(0.02)
        self.assertTrue(t.has_elapsed_in_s(0.01))
        self.assertFalse(t.has_elapsed_in_s(0.03))

    def test_timer_decorator(self):
        """Test Timer functionality as a decorator"""
        decorated_timewaste()
        self.assertTrue(self.is_partially_logged("INFO", "Wasted time: "))


class TestTimers(unittest.TestCase):

    def setUp(self):
        """Set up a Timers instance for use in tests."""
        self.timers = Timers()

    def test_add_and_data_retrieval(self):
        """Test that timings can be added and retrieved."""
        self.timers.add("timer1", 1)
        self.assertEqual(self.timers.data["timer1"], 1)

    def test_clear(self):
        """Test that timings can be cleared."""
        self.timers.add("timer1", 1)
        self.timers.clear()
        self.assertEqual(len(self.timers.data), 0)

    def test_no_assignment(self):
        """Test that assignment is not allowed."""
        with self.assertRaises(TypeError):
            self.timers["timer1"] = 1

    def test_apply_function(self):
        """Test that functions can be applied to timers."""
        self.timers.add("timer1", 1)
        self.timers.add("timer1", 2)
        self.assertEqual(self.timers.apply(sum, "timer1"), 3)

    def test_missing_timer_in_apply(self):
        """Test KeyError when applying function to non-existent timer."""
        with self.assertRaises(KeyError):
            self.timers.apply(sum, "timer1")

    def test_count(self):
        """Test count of timing events."""
        self.timers.add("timer1", 1)
        self.timers.add("timer1", 2)
        self.assertEqual(self.timers.count("timer1"), 2)

    def test_min(self):
        """Test retrieval of minimal value of timings."""
        self.timers.add("timer1", 1)
        self.timers.add("timer1", 2)
        self.assertEqual(self.timers.min("timer1"), 1)

    def test_max(self):
        """Test retrieval of maximum value of timings."""
        self.timers.add("timer1", 1)
        self.timers.add("timer1", 2)
        self.assertEqual(self.timers.max("timer1"), 2)

    def test_mean(self):
        """Test retrieval of mean value of timings."""
        self.timers.add("timer1", 1)
        self.timers.add("timer1", 2)
        self.assertEqual(self.timers.mean("timer1"), 1.5)

    def test_median(self):
        """Test retrieval of median value of timings."""
        self.timers.add("timer1", 1)
        self.timers.add("timer1", 2)
        self.timers.add("timer1", 3)
        self.assertEqual(self.timers.median("timer1"), 2)

    def test_stdev(self):
        """Test retrieval of standard deviation of timings."""
        self.timers.add("timer1", 1)
        self.timers.add("timer1", 2)
        self.timers.add("timer1", 3)
        self.assertEqual(self.timers.stdev("timer1"), 1)

    def test_stdev_with_single_value(self):
        """Test retrieval of standard deviation with single value."""
        self.timers.add("timer1", 1)
        self.assertTrue(math.isnan(self.timers.stdev("timer1")))

    def test_missing_timer_in_statistics(self):
        """Test KeyError when requesting statistics from non-existent timer."""
        with self.assertRaises(KeyError):
            self.timers.count("timer1")

        with self.assertRaises(KeyError):
            self.timers.stdev("timer1")


if __name__ == "__main__":
    unittest.main()
