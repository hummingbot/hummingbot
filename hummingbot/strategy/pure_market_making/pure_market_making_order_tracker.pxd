# distutils: language=c++

from hummingbot.strategy.order_tracker import OrderTracker
from hummingbot.strategy.order_tracker cimport OrderTracker


cdef class PureMarketMakingOrderTracker(OrderTracker):

    cdef c_stop_tracking_limit_order(self, object market_pair, str order_id)
    cdef bint c_check_and_track_cancel(self, str order_id)