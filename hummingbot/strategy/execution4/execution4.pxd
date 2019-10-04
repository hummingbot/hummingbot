# distutils: language=c++

from hummingbot.strategy.strategy_base cimport StrategyBase
from hummingbot.market.market_base cimport MarketBase
from libc.stdint cimport int64_t

cdef class Execution4Strategy(StrategyBase):
    cdef:
        dict _market_infos
        bint _all_markets_ready
        bint _place_orders
        bint _is_buy
        str _order_type

        double _cancel_order_wait_time
        double _last_timestamp
        double _start_timestamp
        double _time_delay
        dict _time_to_cancel
        dict _in_flight_cancels

        double _status_report_interval
        object _order_price
        object _order_amount

        dict _tracked_orders
        dict _order_id_to_market_info

        int64_t _logging_options

        cdef c_process_market(self, object market_info)
        cdef c_place_orders(self, object market_info)
        cdef c_has_enough_balance(self, object market_info)

       
        
