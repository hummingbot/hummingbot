# distutils: language=c++

from libc.stdint cimport int64_t

from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.strategy.strategy_base cimport StrategyBase

from .order_id_market_pair_tracker cimport OrderIDMarketPairTracker


cdef class CrossExchangeMiningStrategy(StrategyBase):
    cdef:
        object _config_map
        set _maker_markets
        set _taker_markets
        bint _all_markets_ready
        bint _adjust_orders_enabled
        dict _anti_hysteresis_timers
        double _last_timestamp
        double _status_report_interval
        dict _order_fill_buy_events
        dict _order_fill_sell_events
        dict _suggested_price_samples
        dict _market_pairs
        int64_t _logging_options
        OrderIDMarketPairTracker _market_pair_tracker
        bint _hb_app_notification
        list _maker_order_ids
        double _last_conv_rates_logged
        object _volatility_pct
        object _balance_timer
        object _volatility_timer
        object _balance_flag
        object _min_prof_adj
        object _min_prof_adj_t
        object _td_bias_min
        object _avg_vol
        object _tol_o
        object _adjcount
        object _limit_order_timer
        bint _maker_side

    cdef check_order(self, object market_pair, object active_order, object is_buy)
    cdef check_balance(self, object market_pair)
    cdef set_order(self, object market_pair, object is_buy)
    cdef str c_place_order(self,
                           object market_pair,
                           bint is_buy,
                           bint is_maker,
                           object amount,
                           object price,
                           bint is_limit)
    cdef volatility_rate(self, object market_pair)

    cdef object adjust_profitability_lag(self, object market_pair)
