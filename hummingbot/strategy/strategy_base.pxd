from hummingbot.core.time_iterator cimport TimeIterator
from hummingbot.core.event.event_listener cimport EventListener

cdef class StrategyBase(TimeIterator):
    cdef:
        set _sb_markets
        EventListener _sb_create_buy_order_listener
        EventListener _sb_create_sell_order_listener
        EventListener _sb_fill_order_listener
        EventListener _sb_fail_order_listener
        EventListener _sb_cancel_order_listener
        EventListener _sb_expire_order_listener
        EventListener _sb_complete_buy_order_listener
        EventListener _sb_complete_sell_order_listener

    cdef c_add_markets(self, list markets)
    cdef c_remove_markets(self, list markets)
    cdef c_did_create_buy_order(self, object order_created_event)
    cdef c_did_create_sell_order(self, object order_created_event)
    cdef c_did_fill_order(self, object order_filled_event)
    cdef c_did_fail_order(self, object order_failed_event)
    cdef c_did_cancel_order(self, object cancelled_event)
    cdef c_did_expire_order(self, object expired_event)
    cdef c_did_complete_buy_order(self, object order_completed_event)
    cdef c_did_complete_sell_order(self, object order_completed_event)
