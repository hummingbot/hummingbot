# distutils: language=c++

from libc.stdint cimport int64_t

from hummingbot.strategy.strategy_py_base cimport StrategyPyBase

cdef class PureMarketMakingStrategyAugmentedPurePython(StrategyPyBase):
    cdef:
        object _market_info

        object _bid_spread
        object _ask_spread
        object _minimum_spread
        object _order_amount
        int _order_levels
        int _buy_levels
        int _sell_levels
        object _split_order_levels_enabled
        object _bid_order_level_spreads
        object _ask_order_level_spreads
        object _order_level_spread
        object _order_level_amount
        double _order_refresh_time
        double _max_order_age
        object _order_refresh_tolerance_pct
        double _filled_order_delay
        bint _inventory_skew_enabled
        object _inventory_target_base_pct
        object _inventory_range_multiplier
        bint _hanging_orders_enabled
        object _hanging_orders_tracker
        bint _order_optimization_enabled
        object _ask_order_optimization_depth
        object _bid_order_optimization_depth
        bint _add_transaction_costs_to_orders
        object _asset_price_delegate
        object _inventory_cost_price_delegate
        object _price_type
        bint _take_if_crossed
        object _price_ceiling
        object _price_floor
        bint _ping_pong_enabled
        list _ping_pong_warning_lines
        bint _hb_app_notification
        object _order_override

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

        object _moving_price_band

    cpdef tick(self, double timestamp)
    cpdef start(self, object clock, double timestamp)
    cpdef stop(self, object clock)
    cpdef all_markets_ready(self)
    cpdef double max_order_age(self)
    cdef apply_inventory_skew(self, object proposal)
    cdef apply_order_optimization(self, object proposal)
    cdef apply_add_transaction_costs(self, object proposal)
    cdef apply_order_levels_modifiers(self, object proposal)
    cdef apply_order_size_modifiers(self, object proposal)
    cdef apply_order_price_modifiers(self, object proposal)
    cdef apply_budget_constraint(self, object proposal)
    cdef apply_ping_pong(self, object proposal)
    cdef apply_price_band(self, object proposal)
    cdef apply_moving_price_band(self, object proposal)
    cdef filter_out_takers(self, object proposal)
    cdef tuple get_adjusted_available_balance(self, list orders)
    cdef object create_base_proposal(self)
    cdef object get_mid_price(self)
    cdef execute_orders_proposal(self, object proposal)
    cdef to_create_orders(self, object proposal)
    cdef cancel_active_orders(self, object proposal)
    cdef cancel_orders_below_min_spread(self)
    cdef cancel_active_orders_on_max_age_limit(self)

    #cpdef object create_base_proposal(self)
