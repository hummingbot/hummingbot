from wings.time_iterator cimport TimeIterator


cdef class StrategyBase(TimeIterator):
    def __init__(self):
        super().__init__()

    cdef active_orders(self):
        raise NotImplementedError

    cdef trades(self):
        raise NotImplementedError

    def format_status(self):
        raise NotImplementedError