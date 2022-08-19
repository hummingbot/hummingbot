# distutils: language=c++

from hummingbot.strategy.order_tracker cimport OrderTracker


cdef class PureMarketMakingOrderTracker(OrderTracker):
    pass
