from .order_pricing_delegate cimport OrderPricingDelegate


cdef class ConstantMultipleSpreadPricingDelegate(OrderPricingDelegate):
    cdef:
        object _bid_spread
        object _ask_spread
        object _order_interval_size
        int _number_of_orders
