# distutils: language=c++

from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t

cdef class HelloWorldStrategy(StrategyBase):
    cdef:
        list _market_pairs
        double _target_amount
        double _target_profitability
        int64_t _logging_options
        double _status_report_interval
        double _refetch_market_info_interval
        bint _all_markets_ready
        double _last_timestamp
        set _markets
        object strategy
        dict _market_info
        set _matching_pairs
        list _target_symbols
        list _equivalent_token
        dict _equivalent_token_dict
        str _discovery_method
        list _fetch_market_info_task_list

    cdef c_process_market_pair(self, object market_pair)
    cdef c_tick(self, double timestamp)
