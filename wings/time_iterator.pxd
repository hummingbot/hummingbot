# distutils: language=c++

from wings.clock cimport Clock

from wings.pubsub cimport PubSub


cdef class TimeIterator(PubSub):
    cdef:
        double _current_timestamp
        Clock _clock

    cdef c_start(self, Clock clock, double timestamp)
    cdef c_stop(self, Clock clock)
    cdef c_tick(self, double timestamp)
