from .order_sizing_delegate cimport OrderSizingDelegate


cdef class ConstantSizeSizingDelegate(OrderSizingDelegate):
    cdef:
        double _order_size
        bint _log_warn
