# distutils: language=c++

from libc.stdint cimport int64_t
from hummingbot.strategy.strategy_base cimport StrategyBase


cdef class BBOStrategy(StrategyBase):
    cdef:
        object _market_info
        object _order_amount
        double _filled_order_delay
        bint _add_transaction_costs_to_orders
        bint _hb_app_notification
        bint _is_debug

        double _cancel_timestamp
        double _create_timestamp
        object _limit_order_type
        bint _all_markets_ready
        int _filled_buys_balance
        int _filled_sells_balance
        double _last_timestamp
        double _status_report_interval
        int64_t _logging_options
        object _last_own_trade_price
        str _debug_csv_path
        double _last_update_time
        int _candle_days
        object _candles
        object _entry_band
        object _exit_band
        double _entry_price
        double _exit_price

    cdef object c_get_mid_price(self)
    cdef c_cancel_active_orders(self, object proposal)
    cdef bint c_is_algorithm_ready(self)
