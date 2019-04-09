from wings.time_iterator cimport TimeIterator


cdef class StrategyBase(TimeIterator):
    def __init__(self):
        super().__init__()

    @property
    def active_orders(self):
        raise NotImplementedError

    @property
    def trades(self):
        raise NotImplementedError

    def format_status(self):
        raise NotImplementedError