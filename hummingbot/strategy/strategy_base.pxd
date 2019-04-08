from wings.time_iterator cimport TimeIterator


cdef class StrategyBase(TimeIterator):
    cdef active_orders(self)
    cdef trades(self)


