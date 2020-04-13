from .order_pricing_delegate cimport OrderPricingDelegate


cdef class ConstantMultipleSpreadPricingDelegate(OrderPricingDelegate):
    cdef:
        object _bid_spread
        object _ask_spread
        object _order_level_spread
        int _order_levels
