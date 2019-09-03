cdef class TransactionTracker(TimeIterator):
    def __init__(self):
        super().__init__()
        self._tx_time_limits = {}

    cdef c_tick(self, double timestamp):
        TimeIterator.c_tick(self, timestamp)
        self.c_process_tx_timeouts()

    cdef c_start_tx_tracking(self, str tx_id, float timeout_seconds):
        if tx_id in self._tx_time_limits:
            raise ValueError(f"The transaction {tx_id} is already being monitored.")
        self._tx_time_limits[tx_id] = self._current_timestamp + timeout_seconds

    cdef c_stop_tx_tracking(self, str tx_id):
        if tx_id not in self._tx_time_limits:
            return
        del self._tx_time_limits[tx_id]

    cdef bint c_is_tx_tracked(self, str tx_id):
        return tx_id in self._tx_time_limits

    cdef c_did_timeout_tx(self, str tx_id):
        self.c_stop_tx_tracking(tx_id)

    cdef c_process_tx_timeouts(self):
        cdef:
            list timed_out_tx_ids = []
        for tx_id, time_limit in self._tx_time_limits.items():
            if self._current_timestamp > time_limit:
                timed_out_tx_ids.append(tx_id)
        for tx_id in timed_out_tx_ids:
            self.c_did_timeout_tx(tx_id)
