# distutils: language=c++

from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t

cdef class SelfTradeStrategy(StrategyBase):
    cdef:
        dict _market_infos
        bint _all_markets_ready
        bint _place_orders

        double _cancel_order_wait_time
        double _status_report_interval
        double _last_timestamp
        double _start_timestamp

        dict _last_trade_timestamp
        dict _time_delay
        dict _min_order_amount
        dict _max_order_amount
        dict _delta_price_changed_percent
        dict _percentage_of_acceptable_price_change
        dict _trade_bands

        object _use_only_oracle_price

        object _last_execute_order_time

        dict _tracked_orders
        dict _time_to_cancel
        dict _order_id_to_market_info
        dict _in_flight_cancels
        object rate_oracle

        int64_t _logging_options

    # cdef object c_get_price(self, object maker_market, str trading_pair)
    cdef c_process_market(self, object market_info)
    cdef c_place_orders(self, object market_info, object is_buy, object order_price, object order_amount)
    cdef c_has_enough_balance(self, object market_info, object is_buy, object order_price, object order_amount)
    cdef c_process_market(self, object market_info)
