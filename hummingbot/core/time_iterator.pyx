# distutils: language=c++


from typing import Optional

from hummingbot.core.clock import Clock

NaN = float("nan")


cdef class TimeIterator(PubSub):
    def __init__(self):
        self._current_timestamp = NaN
        self._clock = None

    cdef c_start(self, Clock clock, double timestamp):
        self.start(clock, clock.current_timestamp)

    cdef c_stop(self, Clock clock):
        self.stop(clock)

    cdef c_tick(self, double timestamp):
        self._current_timestamp = timestamp

    @property
    def current_timestamp(self) -> float:
        return self._current_timestamp

    @property
    def clock(self) -> Optional[Clock]:
        return self._clock

    def start(self, clock: Clock, timestamp: float):
        self._clock = clock
        self._current_timestamp = timestamp

    def stop(self, clock: Clock):
        self._current_timestamp = NaN
        self._clock = None
