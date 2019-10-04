# distutils: language=c++

from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t

cdef class PerformTradeStrategy(StrategyBase):
    cdef:
        dict _market_infos
        bint _all_markets_ready
        bint _place_orders
        bint _is_buy
        str _order_type

        double _status_report_interval
        object _order_price
        object _order_amount

        dict _tracked_orders
        dict _order_id_to_market_info

        int64_t _logging_options

        cdef c_process_market(self, object market_info)
        cdef c_place_order(self, object market_info)
        cdef c_has_enough_balance(self, object market_info)
