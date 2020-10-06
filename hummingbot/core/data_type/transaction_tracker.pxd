from hummingbot.core.time_iterator cimport TimeIterator


cdef class TransactionTracker(TimeIterator):
    cdef:
        dict _tx_time_limits

    cdef c_start_tx_tracking(self, str tx_id, float timeout_seconds)
    cdef c_stop_tx_tracking(self, str tx_id)
    cdef bint c_is_tx_tracked(self, str tx_id)
    cdef c_did_timeout_tx(self, str tx_id)
    cdef c_process_tx_timeouts(self)
