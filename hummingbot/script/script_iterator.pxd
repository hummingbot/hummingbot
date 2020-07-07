# distutils: language=c++

from hummingbot.core.time_iterator cimport TimeIterator


cdef class ScriptIterator(TimeIterator):
    cdef:
        str _script_file_path
        object _strategy
        object _markets
        double _queue_check_interval
        object _event_pairs
        object _did_complete_buy_order_forwarder
        object _did_complete_sell_order_forwarder
        object _script_module
        object _parent_queue
        object _child_queue
        object _ev_loop
        object _script_process
        object _listen_to_child_task
        bint _is_unit_testing_mode
