# distutils: language=c++

from libc.stdint cimport int64_t
from hummingbot.strategy.strategy_base cimport StrategyBase


cdef class PerpetualMarketMakingStrategy(StrategyBase):
    cdef:
        object _market_info
        int _leverage
        object _position_mode
        object _bid_spread
        object _ask_spread
        object _minimum_spread
        object _order_amount
        str _position_management
        object _long_profit_taking_spread
        object _short_profit_taking_spread
        object _ts_activation_spread
        object _ts_callback_rate
        object _stop_loss_spread
        object _close_position_order_type
        object _close_order_type
        double _next_buy_exit_order_timestamp
        double _next_sell_exit_order_timestamp
        int _order_levels
        int _buy_levels
        int _sell_levels
        object _order_level_spread
        object _order_level_amount
        double _order_refresh_time
        object _order_refresh_tolerance_pct
        double _filled_order_delay
        bint _hanging_orders_enabled
        object _hanging_orders_cancel_pct
        bint _order_optimization_enabled
        object _ask_order_optimization_depth
        object _bid_order_optimization_depth
        bint _add_transaction_costs_to_orders
        object _asset_price_delegate
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
        list _hanging_order_ids
        double _last_timestamp
        double _status_report_interval
        int64_t _logging_options
        object _last_own_trade_price
        object _ts_peak_bid_price
        object _ts_peak_ask_price
        list _exit_orders
    cdef c_manage_positions(self, list session_positions)
    cdef c_profit_taking_feature(self, object mode, list active_positions)
    cdef c_trailing_stop_feature(self, object mode, list active_positions)
    cdef c_stop_loss_feature(self, object mode, list active_positions)
    cdef c_apply_initial_settings(self, str trading_pair, object position, int64_t leverage)
    cdef object c_get_mid_price(self)
    cdef object c_create_base_proposal(self)
    cdef tuple c_get_adjusted_available_balance(self, list orders)
    cdef c_apply_order_levels_modifiers(self, object proposal)
    cdef c_apply_price_band(self, object proposal)
    cdef c_apply_ping_pong(self, object proposal)
    cdef c_apply_order_price_modifiers(self, object proposal)
    cdef c_apply_budget_constraint(self, object proposal)
    cdef c_filter_out_takers(self, object proposal)
    cdef c_apply_order_optimization(self, object proposal)
    cdef c_apply_add_transaction_costs(self, object proposal)
    cdef bint c_is_within_tolerance(self, list current_prices, list proposal_prices)
    cdef c_cancel_active_orders(self, object proposal)
    cdef c_cancel_hanging_orders(self)
    cdef c_cancel_orders_below_min_spread(self)
    cdef bint c_to_create_orders(self, object proposal)
    cdef c_execute_orders_proposal(self, object proposal, object position_action)
    cdef set_timers(self)
