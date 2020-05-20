from .order_pricing_delegate cimport OrderPricingDelegate


cdef class ConstantSpreadPricingDelegate(OrderPricingDelegate):
    cdef:
        object _bid_spread
        object _ask_spread
