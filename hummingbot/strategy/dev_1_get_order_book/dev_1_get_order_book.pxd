# distutils: language=c++

from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t

cdef class GetOrderBookStrategy(StrategyBase):
    cdef:
        dict _market_infos
        bint _all_markets_ready
        double _status_report_interval
        int64_t _logging_options
