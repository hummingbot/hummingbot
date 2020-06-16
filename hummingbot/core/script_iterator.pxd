# distutils: language=c++

from hummingbot.core.time_iterator cimport TimeIterator
from hummingbot.core.clock cimport Clock

cdef class ScriptIterator(TimeIterator):
    cdef:
        str _start_script
        str _tick_script
        str _buy_order_completed_script
        str _sell_order_completed_script
        object _strategy
        object _variables
        object _markets
        object _event_pairs
        object _did_complete_buy_order_forwarder
        object _did_complete_sell_order_forwarder
