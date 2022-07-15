# distutils: language=c++

from hummingbot.core.clock cimport Clock
from hummingbot.core.pubsub cimport PubSub


cdef class TimeIterator(PubSub):
    cdef:
        double _current_timestamp
        Clock _clock
        double _overriding_tick

    cdef c_start(self, Clock clock, double timestamp)
    cdef c_stop(self, Clock clock)
    cdef c_tick(self, double timestamp)
