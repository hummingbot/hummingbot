# distutils: language=c++

from hummingbot.strategy.strategy_base cimport StrategyBase
from hummingbot.market.market_base cimport MarketBase
from libc.stdint cimport int64_t

cdef class SimpleTradeStrategy(StrategyBase):
    cdef:
        dict _market_infos
        bint _all_markets_ready
        bint _place_orders
        bint _is_buy
        str _order_type


        double _cancel_order_wait_time
        double _status_report_interval
        double _last_timestamp
        double _start_timestamp
        double _time_delay
        double _order_price
        double _order_amount

        dict _tracked_orders
        dict _time_to_cancel
        dict _order_id_to_market_info
        dict _in_flight_cancels

        int64_t _logging_options


    cdef c_process_market(self, object market_info)
    cdef c_tick(self, double timestamp)
    cdef c_cancel_order(self, object market_info, str order_id)
    cdef c_place_orders(self, object market_info)
    cdef c_has_enough_balance(self, object market_info)
    cdef c_process_market(self, object market_info)
