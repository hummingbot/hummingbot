# distutils: language=c++

from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t

cdef class StonesWithPaybackStrategy(StrategyBase):
    cdef:
        dict _market_infos
        bint _all_markets_ready
        bint _place_orders
        list buy_levels
        list sell_levels
        dict map_order_id_to_level
        dict _total_buy_order_amount
        dict _total_sell_order_amount
        dict _last_opened_order_timestamp
        dict _payback_info
        dict map_order_id_to_oracle_price
        object rate_oracle
        object percentage_price_shift_during_payback

        double _status_report_interval
        double _last_timestamp
        double _start_timestamp
        double _time_delay

        dict _tracked_orders
        dict _time_to_cancel
        dict _order_id_to_market_info
        dict _in_flight_cancels

        int64_t _logging_options

    # cdef object c_get_price(self, object maker_market, str trading_pair)
    cdef c_process_market(self, object market_info)
    cdef c_place_orders(self, object market_info, object is_buy, object order_price, object order_amount)
    cdef c_has_enough_balance(self, object market_info, object is_buy, object order_price, object order_amount)
    cdef c_process_market(self, object market_info)
