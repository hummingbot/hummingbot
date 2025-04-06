# distutils: language=c++

from libc.stdint cimport int64_t
from hummingbot.strategy.__utils__.trailing_indicators.trading_intensity cimport TradingIntensityIndicator
from hummingbot.strategy.strategy_base cimport StrategyBase


cdef class AvellanedaMarketMakingStrategy(StrategyBase):
    cdef:
        object _config_map
        object _market_info
        object _price_delegate
        object _minimum_spread
        bint _hanging_orders_enabled
        object _hanging_orders_cancel_pct
        object _hanging_orders_tracker
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
        int _volatility_sampling_period
        double _last_sampling_timestamp
        bint _parameters_based_on_spread
        int _volatility_buffer_size
        int _trading_intensity_buffer_size
        int _ticks_to_be_ready
        object _alpha
        object _kappa
        object _gamma
        object _eta
        str _execution_mode
        str _execution_timeframe
        object _execution_state
        object _start_time
        object _end_time
        double _min_spread
        object _q_adjustment_factor
        object _reservation_price
        object _optimal_spread
        object _optimal_bid
        object _optimal_ask
        str _debug_csv_path
        object _avg_vol
        TradingIntensityIndicator _trading_intensity
        bint _should_wait_order_cancel_confirmation

    cdef object c_get_mid_price(self)
    cdef _create_proposal_based_on_order_levels(self)
    cdef _create_proposal_based_on_order_override(self)
    cdef _create_basic_proposal(self)
    cdef object c_create_base_proposal(self)
    cdef tuple c_get_adjusted_available_balance(self, list orders)
    cdef c_apply_order_price_modifiers(self, object proposal)
    cdef c_apply_order_amount_eta_transformation(self, object proposal)
    cdef c_apply_budget_constraint(self, object proposal)
    cdef c_apply_order_optimization(self, object proposal)
    cdef c_apply_add_transaction_costs(self, object proposal)
    cdef bint c_is_within_tolerance(self, list current_prices, list proposal_prices)
    cdef c_cancel_active_orders(self, object proposal)
    cdef c_cancel_active_orders_on_max_age_limit(self)
    cdef bint c_to_create_orders(self, object proposal)
    cdef c_execute_orders_proposal(self, object proposal)
    cdef c_set_timers(self)
    cdef double c_get_spread(self)
    cdef c_collect_market_variables(self, double timestamp)
    cdef bint c_is_algorithm_ready(self)
    cdef bint c_is_algorithm_changed(self)
    cdef c_measure_order_book_liquidity(self)
    cdef c_calculate_reservation_price_and_optimal_spread(self)
    cdef object c_calculate_target_inventory(self)
    cdef object c_calculate_inventory(self)
    cdef c_did_complete_order(self, object order_completed_event)
