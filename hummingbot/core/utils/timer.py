"""Implements a Timer. It constrains the use of nanoseconds (int) internally for
time counting purpose. The preferred time function is perf_counter_ns() (set as default)

Original package available at https://pypi.org/project/codetiming/
forked and tuned from: https://github.com/realpython/codetiming

This module uses the aliases (defined in the _timers.py):
    _NANOSECONDS: int
    _SECONDS: Decimal

Classes:
    Timer: Time counting class

Timer class: useful functions provided by this class
    start(): Starts the timer (using time.perf_counter_ns() as internal time measure)
    split_in_ns(): Returns the instantaneous nanoseconds split of the running Timer
        Raises a TimeError exception is the Timer is not started
    split_in_s(): Returns the seconds split of the running Timer
        Raises a TimeError exception is the Timer is not started
    stop(): Stops the timer, logs the stop time register the stop time in ns,
        returns the stop time in s
        Raises an error if called with a stopped Timer
    has_elapsed_in_s(duration): Returns whether the Timer has run longer than the
        `duration` argument
"""

import logging
import time
from contextlib import ContextDecorator
from decimal import Decimal
from typing import Any, Callable, ClassVar, Optional, Sequence, Tuple, Union, cast

from hummingbot.logger.logger import HummingbotLogger

from .timers import _NANOSECONDS, _SECONDS, Timers


class TimerNotStartedError(Exception):
    """The Timer has not been started. Use .start() to start it"""


class TimerAlreadyStartedError(Exception):
    """The Timer is already started"""


class Timer(ContextDecorator):
    """Time your code using a class, context manager, or decorator"""

    timers: Timers = Timers()
    _logger: ClassVar[logging.Logger] = None

    __slots__ = (
        '_start_time',
        '_last',
        '_time_counter_ns',
        'name',
        'text'
    )

    def __init__(self, name: str = None,
                 text: Union[str, Callable[[_SECONDS], str]] = "Elapsed time: {:0.4f} seconds",
                 timer_ns: Callable[..., _NANOSECONDS] = time.perf_counter_ns):
        self._start_time: Optional[_NANOSECONDS] = None
        self._last: Union[_NANOSECONDS, _SECONDS] = Decimal("NaN")
        self._time_counter_ns: Callable[..., _NANOSECONDS] = timer_ns

        self.name: str = name
        self.text: Union[str, Callable[[_SECONDS], str]] = text

    @property
    def last(self) -> Union[_NANOSECONDS, _SECONDS]:
        """
        Returns the last stop in nanoseconds. Returns Decimal("NaN") if the
        Timer is not started or has not been stopped

        :returns: Last stop time in nanoseconds
        :rtype: Union[_NANOSECONDS, _SECONDS]
        """
        return self._last

    @classmethod
    def logger(cls) -> HummingbotLogger:
        """
        Provides access to Hummingbot logger

        :returns: Hummingbot logger handle
        :rtype: HummingbotLogger
        """
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cast(HummingbotLogger, cls._logger)

    def _now(self) -> _NANOSECONDS:
        """
        Returns the current system time (using time.perf_counter_ns() by default)

        :returns: Current OS time in nanoseconds
        :rtype: _NANOSECONDS
        """
        return self._time_counter_ns()

    @property
    def _last_in_s(self) -> _SECONDS:
        """
        Returns the last stop in seconds. Returns Decimal("NaN") if the
        Timer is not started or has not been stopped

        :returns: Last stop time in seconds
        :rtype: _SECONDS
        """
        return self._last * _SECONDS("1e-9")

    def _raise_if_not_started(self) -> bool:
        """
        Checks whether the Timer is started, raises a TimeError if not

        :returns: True, if Timer is started
        :rtype: bool
        :raises TimerError: if Timer is not started
        """
        if self._start_time is None:
            raise TimerNotStartedError
        return True

    def has_elapsed_in_s(self, value: Union[Decimal, float, str, Tuple[int, Sequence[int], int]]) -> bool:
        """
        Checks if many seconds have elapsed since start

        :param Union[Decimal, float, str, Tuple[int, Sequence[int], int]] value: Duration to check the Timer against
        :returns: Whether the Timer has run longer than the argument
        :rtype: bool
        :raises TimerError: if Timer is not started
        """
        if self._start_time is None:
            return False
        return Decimal(value) < self.split_in_s()

    def start(self) -> None:
        """
        Starts the Timer

        :raises TimerError: if Timer is already started
        """
        if self._start_time is not None:
            raise TimerAlreadyStartedError
        self._start_time: _NANOSECONDS = self._now()

    def split_in_ns(self, record: bool = False) -> _NANOSECONDS:
        """
        Provides the instantaneous split time in nanoseconds. Records the split
        if requested (defaults to False)

        :param bool record: Whether to record the split (default is False)
        :returns: Split time in nanoseconds
        :rtype: _NANOSECONDS
        :raises TimerError: if Timer is not started
        """
        self._raise_if_not_started()
        elapsed: _NANOSECONDS = self._now() - self._start_time
        if record and self.name:
            self.timers.add(self.name, elapsed)
        return elapsed

    def split_in_s(self, record: bool = False) -> _SECONDS:
        """
        Provides the instantaneous split time in seconds. Records the split
        if requested (defaults to False)

        :param bool record: Whether to record the split (default is False)
        :returns: Split time in seconds
        :rtype: _SECONDS
        :raises TimerError: if Timer is not started
        """
        return self.split_in_ns(record) * _SECONDS("1e-9")

    def stop(self) -> _SECONDS:
        """
        Stops the Timer, records the stop time, returns the stop time in seconds

        :returns: Split time in seconds
        :rtype: _SECONDS
        :raises TimerError: if Timer is not started
        """
        self._raise_if_not_started()

        # Calculate elapsed time
        self._last = self._now() - self._start_time
        self._start_time = None

        # Report elapsed time
        if self.logger:
            if callable(self.text):
                text = self.text(self._last_in_s)
            else:
                attributes = {
                    "name": self.name,
                    "milliseconds": self._last_in_s * Decimal("1000"),
                    "seconds": self._last_in_s,
                    "minutes": self._last_in_s / Decimal("60"),
                }
                text = self.text.format(self._last_in_s, **attributes)
            self.logger().info(text)
        if self.name:
            self.timers.add(self.name, self._last)

        return self._last_in_s

    def __enter__(self) -> "Timer":
        """Start a new timer as a context manager"""
        self.start()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        """Stop the context manager timer"""
        self.stop()
