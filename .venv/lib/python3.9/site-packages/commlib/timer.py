import threading
import time
from typing import Callable

from commlib.utils import Rate


class TimerEvent:
    def __init__(
        self,
        last_expected: float,
        last_real: float,
        current_expected: float,
        current_real: float,
        last_duration: float):
        """__init__.

        Args:
            last_expected (float): last_expected
            last_real (float): last_real
            current_expected (float): current_expected
            current_real (float): current_real
            last_duration (float): last_duration
        """
        self.last_expected = last_expected
        self.last_real = last_real
        self.current_expected = current_expected
        self.current_real = current_real
        self.last_duration = last_duration


class Timer(threading.Thread):
    def __init__(self, period: float, callback: Callable, oneshot: bool = False):
        """__init__.

        Args:
            period (float): period
            callback (Callable): callback
            oneshot (bool): oneshot
        """
        super().__init__()
        self._period = period
        self._callback = callback
        self._oneshot = oneshot
        self._shutdown = False
        self.daemon = True

    def shutdown(self):
        """shutdown.
        Marks the timer as shutdown, causing the timer loop to exit on the next iteration.
        """

        self._shutdown = True

    def run(self):
        """run.
        Runs the timer loop, calling the provided callback function at the specified period.

        The timer loop sleeps for the specified period using the `Rate` utility, then calls the provided callback function with a `TimerEvent` object containing information about the last and current timer events.

        If `oneshot` is `True`, the timer will only fire the callback once and then stop. Otherwise, the timer will continue to fire the callback indefinitely until `shutdown()` is called.

        The `TimerEvent` object passed to the callback function contains the following information:
        - `last_expected`: The expected time of the last timer event.
        - `last_real`: The actual time of the last timer event.
        - `current_expected`: The expected time of the current timer event.
        - `current_real`: The actual time of the current timer event.
        - `last_duration`: The duration of the last timer event.
        """

        r = Rate(1.0 / self._period)
        current_expected = time.time() + self._period
        last_expected, last_real, last_duration = None, None, None
        while True:
            try:
                r.sleep()
            except KeyboardInterrupt as exc:
                print(exc)
                break
            if self._shutdown:
                break
            start = time.time()
            current_real = start
            self._callback(
                TimerEvent(
                    last_expected,
                    last_real,
                    current_expected,
                    current_real,
                    last_duration,
                )
            )
            if self._oneshot:
                break
            last_duration = time.time() - start
            last_expected, last_real = current_expected, current_real
            current_expected += self._period
