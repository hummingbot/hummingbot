# distutils: language=c++

from libc.stdint cimport int64_t
from hummingbot.strategy.strategy_base cimport StrategyBase
from .aroon_oscillator_indicator cimport AroonOscillatorIndicator


cdef class AroonOscillatorStrategy(StrategyBase):
    cdef:
        object _market_info

        object _bid_spread
        object _ask_spread
        object _minimum_spread
        object _maximum_spread
        object _order_amount
        int _order_levels
        int _buy_levels
        int _sell_levels
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
        object _hanging_orders_cancel_pct
        bint _order_optimization_enabled
        object _ask_order_optimization_depth
        object _bid_order_optimization_depth
        bint _add_transaction_costs_to_orders
        object _price_type
        bint _take_if_crossed
        object _price_ceiling
        object _price_floor
        bint _hb_app_notification
        object _order_override
        int _period_length
        int _period_duration
        int _minimum_periods
        object _cancel_order_spread_threshold
        object _aroon_osc_strength_factor

        double _cancel_timestamp
        double _create_timestamp
        object _limit_order_type
        bint _all_markets_ready
        int _filled_buys_balance
        int _filled_sells_balance
        list _hanging_order_ids
        double _last_timestamp
        double _status_report_interval
        int64_t _logging_options
        object _last_own_trade_price
        list _hanging_aged_order_prices
        object _min_max_spread_diff
        object _ask_increase
        object _bid_increase
        object _trend_factor
        str _debug_csv_path
        bint _is_debug

        AroonOscillatorIndicator _aroon_osc

    cdef object c_get_mid_price(self)
    cdef object c_create_base_proposal(self)
    cdef tuple c_get_adjusted_available_balance(self, list orders)
    cdef c_adjust_spreads(self)
    cdef c_apply_order_levels_modifiers(self, object proposal)
    cdef c_apply_price_band(self, object proposal)
    cdef c_apply_order_price_modifiers(self, object proposal)
    cdef c_apply_order_size_modifiers(self, object proposal)
    cdef c_apply_inventory_skew(self, object proposal)
    cdef c_apply_budget_constraint(self, object proposal)

    cdef c_filter_out_takers(self, object proposal)
    cdef c_apply_order_optimization(self, object proposal)
    cdef c_apply_add_transaction_costs(self, object proposal)
    cdef bint c_is_within_tolerance(self, list current_prices, list proposal_prices)
    cdef c_cancel_active_orders(self, object proposal)
    cdef c_cancel_hanging_orders(self)
    cdef c_cancel_orders_below_min_spread(self)
    cdef c_aged_order_refresh(self)
    cdef bint c_to_create_orders(self, object proposal)
    cdef c_execute_orders_proposal(self, object proposal)
    cdef set_timers(self)
