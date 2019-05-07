from wings.time_iterator cimport TimeIterator
from wings.event_listener cimport EventListener


cdef class StrategyBase(TimeIterator):
    pass