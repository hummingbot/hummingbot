# distutils: language=c++

from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t

cdef class DiscoveryStrategy(StrategyBase):
    cdef:
        list _market_pairs
        double _target_amount
        double _target_profitability
        int64_t _logging_options
        double _status_report_interval
        double _refetch_market_info_interval
        bint _all_markets_ready
        double _last_timestamp
        object strategy
        dict _discovery_stats
        dict _market_info
        set _matching_pairs
        list _target_trading_pairs
        list _equivalent_token
        dict _equivalent_token_dict
        str _discovery_method
        list _fetch_market_info_task_list

    cdef c_process_market_pair(self, object market_pair)
    cdef c_tick(self, double timestamp)
    cdef object c_calculate_arbitrage_discovery(self,
                                              object market_pair,
                                              set matching_pairs,
                                              double target_amount,
                                              double target_profitability)
    cdef c_calculate_market_stats(self, object market_pair, dict exchange_market_info)
    cdef dict c_calculate_single_arbitrage_profitability(self,
                                                         object market_pair,
                                                         tuple matching_pair,
                                                         double target_amount=*,
                                                         double target_profitability=*)
