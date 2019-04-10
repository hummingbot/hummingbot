from wings.time_iterator cimport TimeIterator
from wings.event_listener cimport EventListener


cdef class StrategyBase(TimeIterator):
    cdef:
        EventListener _trade_listener
        object _past_trades

    cdef c_record_trade(self, object order_filled_event)