from .order_sizing_delegate cimport OrderSizingDelegate

cdef class StaggeredMultipleSizeSizingDelegate(OrderSizingDelegate):
    cdef:
        double _order_step_size
        double _order_start_size
        int _number_of_orders
        bint _log_warn
