# distutils: language=c++


from typing import Optional

from wings.clock import Clock


cdef class TimeIterator(PubSub):
    def __init__(self):
        self._current_timestamp = float("NaN")
        self._clock = None

    cdef c_start(self, Clock clock, double timestamp):
        self._clock = clock
        self._current_timestamp = timestamp

    cdef c_tick(self, double timestamp):
        self._current_timestamp = timestamp

    @property
    def current_timestamp(self) -> float:
        return self._current_timestamp

    @property
    def clock(self) -> Optional[Clock]:
        return self._clock

    def start(self, clock: Clock):
        self.c_start(clock, clock.current_timestamp)