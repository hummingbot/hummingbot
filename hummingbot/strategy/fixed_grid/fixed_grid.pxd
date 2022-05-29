# distutils: language=c++

from libc.stdint cimport int64_t

from hummingbot.strategy.strategy_base cimport StrategyBase


cdef class FixedGridStrategy(StrategyBase):
    cdef:
        object _market_info

        int _n_levels
        object _grid_price_ceiling
        object _grid_price_floor
        object _order_amount
        object _start_order_spread
        double _order_refresh_time
        double _max_order_age
        object _order_refresh_tolerance_pct
        bint _order_optimization_enabled
        object _ask_order_optimization_depth
        object _bid_order_optimization_depth
        bint _take_if_crossed
        bint _hb_app_notification

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
        bint _should_wait_order_cancel_confirmation
        double _filled_order_delay

        list _price_levels
        list _base_inv_levels
        list _quote_inv_levels 
        list _quote_inv_levels_current_price
        int _current_level
        object _grid_spread 
        bint _inv_correct
        object _start_order_amount 
        bint _start_order_buy 


    cdef object c_get_mid_price(self)
    cdef object c_create_rebalance_proposal(self)
    cdef object c_create_grid_proposal(self)
    cdef tuple c_get_adjusted_available_balance(self, list orders)
    cdef c_apply_order_price_modifiers(self, object proposal)
    cdef c_filter_out_takers(self, object proposal)
    cdef c_apply_order_optimization(self, object proposal)
    cdef bint c_is_within_tolerance(self, list current_prices, list proposal_prices)
    cdef c_cancel_active_orders(self, object proposal)
    cdef c_cancel_active_orders_on_max_age_limit(self)
    cdef bint c_to_create_orders(self, object proposal)
    cdef c_execute_orders_proposal(self, object proposal)
    cdef set_timers(self)
