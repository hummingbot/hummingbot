# distutils: language=c++

from hummingbot.core.time_iterator cimport TimeIterator


cdef class NetworkIterator(TimeIterator):
    cdef:
        object _network_status
        double _last_connected_timestamp
        double _check_network_interval
        double _check_network_timeout
        double _network_error_wait_time
        object _check_network_task
