# distutils: language=c++

from hummingbot.strategy.strategy_base cimport StrategyBase
from hummingbot.market.market_base cimport MarketBase
from libc.stdint cimport int64_t

cdef class Dev5TwapTradeStrategy(StrategyBase):
    cdef:
        dict _market_infos
        bint _all_markets_ready
        bint _place_orders
        bint _is_buy
        str _order_type

        double _cancel_order_wait_time
        double _status_report_interval
        double _last_timestamp
        double _previous_timestamp
        double _time_delay
        int _num_individual_orders
        double _order_price
        object _order_amount
        object _quantity_remaining
        bint _first_order
        bint _is_vwap
        double _percent_slippage
        double _order_percent_of_volume
        bint _has_outstanding_order

        dict _tracked_orders
        dict _time_to_cancel
        dict _order_id_to_market_info
        dict _in_flight_cancels

        int64_t _logging_options

    cdef c_check_last_order(self, object order_event)
    cdef c_process_market(self, object market_info)
    cdef c_place_orders(self, object market_info)
    cdef c_has_enough_balance(self, object market_info)
    cdef c_process_market(self, object market_info)
