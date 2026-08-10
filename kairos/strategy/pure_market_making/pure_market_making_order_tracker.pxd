# distutils: language=c++

from kairos.strategy.order_tracker import OrderTracker
from kairos.strategy.order_tracker cimport OrderTracker


cdef class PureMarketMakingOrderTracker(OrderTracker):
    pass
