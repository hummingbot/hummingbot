from .order_sizing_delegate cimport OrderSizingDelegate


cdef class ConstantMultipleSizeSizingDelegate(OrderSizingDelegate):
    cdef:
        double _order_size
        int _number_of_orders
