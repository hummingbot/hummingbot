from .order_sizing_delegate cimport OrderSizingDelegate

cdef class StaggeredMultipleSizeSizingDelegate(OrderSizingDelegate):
    cdef:
        object _order_step_size
        object _order_start_size
        int _number_of_orders
        bint _log_warning_order_size
        bint _log_warning_balance
