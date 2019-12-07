# distutils: language=c++

from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t

cdef class HelloWorldStrategy(StrategyBase):
    cdef:
        dict _market_infos
        str _asset_trading_pair
        bint _all_markets_ready
        double _status_report_interval
        int64_t _logging_options
