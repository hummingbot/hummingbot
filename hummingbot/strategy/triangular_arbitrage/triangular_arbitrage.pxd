# distutils: language=c++

from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t


cdef class TriangularArbitrageStrategy(StrategyBase):
    cdef:
        list _market_pairs
        bint _all_markets_ready
        bint _execution_processing
        bint _recent_failure
        double _status_report_interval
        double _next_trade_delay
        double _last_timestamp
        double _last_failure_timestamp
        double _failure_delay_interval
        int64_t _logging_options
        object _triangular_arbitrage_module
        object _arbitrage_execution_tracker
        dict _trading_pair_to_market_pair_tuple
        int _failed_market_order_count
        int _failed_order_tolerance
        object _arbitrage_opportunity

    cdef _did_create_order(self, object order_created_event)
    cdef _did_complete_order(self, object completed_event)
    cdef c_execute_opportunity(self, object arbitrage_opportunity)