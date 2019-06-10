from .order_pricing_delegate cimport OrderPricingDelegate


cdef class ConstantSpreadPricingDelegate(OrderPricingDelegate):
    cdef:
        double _bid_spread
        double _ask_spread