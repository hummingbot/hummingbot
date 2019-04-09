from typing import List
from wings.time_iterator cimport TimeIterator
from wings.limit_order cimport LimitOrder
from wings.trade import Trade


cdef class StrategyBase(TimeIterator):
    def __init__(self):
        super().__init__()

    @property
    def active_orders(self) -> List[LimitOrder]:
        raise NotImplementedError

    @property
    def trades(self) -> List[Trade]:
        raise NotImplementedError

    def format_status(self):
        raise NotImplementedError