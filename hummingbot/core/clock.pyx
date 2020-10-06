# distutils: language=c++

import asyncio
import logging
import time
from typing import List

from hummingbot.core.time_iterator import TimeIterator
from hummingbot.core.time_iterator cimport TimeIterator
from hummingbot.core.clock_mode import ClockMode
from hummingbot.logger import HummingbotLogger

s_logger = None


cdef class Clock:
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self, clock_mode: ClockMode, tick_size: float = 1.0, start_time: float = 0.0, end_time: float = 0.0):
        """
        :param clock_mode: either real time mode or back testing mode
        :param tick_size: time interval of each tick
        :param start_time: (back testing mode only) start of simulation in UNIX timestamp
        :param end_time: (back testing mode only) end of simulation in UNIX timestamp. NaN to simulate to end of data.
        """
        self._clock_mode = clock_mode
        self._tick_size = tick_size
        self._start_time = start_time
        self._end_time = end_time
        self._current_tick = start_time if clock_mode is ClockMode.BACKTEST else (time.time() // tick_size) * tick_size
        self._child_iterators = []
        self._current_context = None
        self._started = False

    @property
    def clock_mode(self) -> ClockMode:
        return self._clock_mode

    @property
    def start_time(self) -> float:
        return self._start_time

    @property
    def tick_size(self) -> float:
        return self._tick_size

    @property
    def child_iterators(self) -> List[TimeIterator]:
        return self._child_iterators

    @property
    def current_timestamp(self) -> float:
        return self._current_tick

    def __enter__(self) -> Clock:
        if self._current_context is not None:
            raise EnvironmentError("Clock context is not re-entrant.")
        self._current_context = self._child_iterators.copy()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._current_context is not None:
            for iterator in self._current_context:
                (<TimeIterator>iterator).c_stop(self)
        self._current_context = None

    def add_iterator(self, iterator: TimeIterator):
        if self._current_context is not None:
            self._current_context.append(iterator)
        if self._started:
            (<TimeIterator>iterator).c_start(self, self._current_tick)
        self._child_iterators.append(iterator)

    def remove_iterator(self, iterator: TimeIterator):
        if self._current_context is not None and iterator in self._current_context:
            (<TimeIterator>iterator).c_stop(self)
            self._current_context.remove(iterator)
        self._child_iterators.remove(iterator)

    async def run(self):
        await self.run_til(float("nan"))

    async def run_til(self, timestamp: float):
        cdef:
            TimeIterator child_iterator
            double now = time.time()
            double next_tick_time

        if self._current_context is None:
            raise EnvironmentError("run() and run_til() can only be used within the context of a `with...` statement.")

        self._current_tick = (now // self._tick_size) * self._tick_size
        if not self._started:
            for ci in self._current_context:
                child_iterator = ci
                child_iterator.c_start(self, self._current_tick)
            self._started = True

        try:
            while True:
                now = time.time()
                if now >= timestamp:
                    return

                # Sleep until the next tick
                next_tick_time = ((now // self._tick_size) + 1) * self._tick_size
                await asyncio.sleep(next_tick_time - now)
                self._current_tick = next_tick_time

                # Run through all the child iterators.
                for ci in self._current_context:
                    child_iterator = ci
                    try:
                        child_iterator.c_tick(self._current_tick)
                    except StopIteration:
                        self.logger().error("Stop iteration triggered in real time mode. This is not expected.")
                        return
                    except Exception:
                        self.logger().error("Unexpected error running clock tick.", exc_info=True)
        finally:
            for ci in self._current_context:
                child_iterator = ci
                child_iterator._clock = None

    def backtest_til(self, timestamp: float):
        cdef TimeIterator child_iterator

        if not self._started:
            for ci in self._child_iterators:
                child_iterator = ci
                child_iterator.c_start(self, self._start_time)
            self._started = True

        try:
            while not (self._current_tick >= timestamp):
                self._current_tick += self._tick_size
                for ci in self._child_iterators:
                    child_iterator = ci
                    try:
                        child_iterator.c_tick(self._current_tick)
                    except StopIteration:
                        raise
                    except Exception:
                        self.logger().error("Unexpected error running clock tick.", exc_info=True)
        except StopIteration:
            return
        finally:
            for ci in self._child_iterators:
                child_iterator = ci
                child_iterator._clock = None

    def backtest(self):
        self.backtest_til(self._end_time)
