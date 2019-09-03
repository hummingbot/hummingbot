from .order_filter_delegate cimport OrderFilterDelegate


cdef class PassThroughFilterDelegate(OrderFilterDelegate):
    pass