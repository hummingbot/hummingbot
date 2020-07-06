# distutils: language=c++

from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.time_iterator cimport TimeIterator


cdef class OrderTracker(TimeIterator):
    cdef:
        dict _tracked_limit_orders
        dict _tracked_market_orders
        dict _order_id_to_market_pair
        dict _shadow_tracked_limit_orders
        dict _shadow_order_id_to_market_pair
        object _shadow_gc_requests
        object _in_flight_cancels
        object _in_flight_pending_created

    cdef dict c_get_limit_orders(self)
    cdef dict c_get_market_orders(self)
    cdef dict c_get_shadow_limit_orders(self)
    cdef bint c_has_in_flight_cancel(self, str order_id)
    cdef bint c_check_and_track_cancel(self, str order_id)
    cdef object c_get_market_pair_from_order_id(self, str order_id)
    cdef object c_get_shadow_market_pair_from_order_id(self, str order_id)
    cdef LimitOrder c_get_limit_order(self, object market_pair, str order_id)
    cdef object c_get_market_order(self, object market_pair, str order_id)
    cdef LimitOrder c_get_shadow_limit_order(self, str order_id)
    cdef c_start_tracking_limit_order(self, object market_pair, str order_id, bint is_buy, object price,
                                      object quantity)
    cdef c_stop_tracking_limit_order(self, object market_pair, str order_id)
    cdef c_start_tracking_market_order(self, object market_pair, str order_id, bint is_buy, object quantity)
    cdef c_stop_tracking_market_order(self, object market_pair, str order_id)
    cdef c_check_and_cleanup_shadow_records(self)
    cdef c_add_create_order_pending(self, str order_id)
    cdef c_remove_create_order_pending(self, str order_id)
