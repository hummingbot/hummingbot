from .order_filter_delegate cimport OrderFilterDelegate
from libc.stdint cimport int64_t


cdef class PassThroughFilterDelegate(OrderFilterDelegate):
    cdef:
        double _order_placing_timestamp
