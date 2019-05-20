from hummingbot.core.time_iterator cimport TimeIterator


cdef class SQLKeepAlive(TimeIterator):
    cdef:
        object _sql
        double _last_timestamp
        int _tick_size