from hummingbot.core.time_iterator cimport TimeIterator


cdef class OrderIDMarketPairTracker(TimeIterator):
    cdef:
        object _order_id_to_tracking_item
        float _expiry_timeout

    cdef object c_get_market_pair_from_order_id(self, str order_id)
    cdef object c_get_exchange_from_order_id(self, str order_id)
    cdef c_start_tracking_order_id(self, str order_id, object exchange, object market_pair)
    cdef c_stop_tracking_order_id(self, str order_id)
    cdef c_check_and_expire_tracking_items(self)
