# distutils: language=c++

from libc.stdint cimport int64_t

from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.strategy.strategy_base cimport StrategyBase

from .order_id_market_pair_tracker cimport OrderIDMarketPairTracker

cdef class CrossExchangeMarketMakingStrategy(StrategyBase):
    cdef:
        dict _market_pairs
        set _maker_markets
        set _taker_markets
        bint _all_markets_ready
        dict _anti_hysteresis_timers
        double _min_profitability
        double _order_size_taker_volume_factor
        double _order_size_taker_balance_factor
        double _order_size_portfolio_ratio_limit
        double _anti_hysteresis_duration
        double _status_report_interval
        double _last_timestamp
        double _trade_size_override
        double _cancel_order_threshold
        bint _active_order_canceling
        dict _order_fill_buy_events
        dict _order_fill_sell_events
        dict _suggested_price_samples
        int64_t _logging_options
        # double _hedging_price_adjustment_factor
        object _exchange_rate_conversion
        OrderIDMarketPairTracker _market_pair_tracker

    cdef c_process_market_pair(self,
                               object market_pair,
                               list active_ddex_orders)
    cdef c_check_and_hedge_orders(self,
                                  object market_pair)
    cdef object c_get_order_size_after_portfolio_ratio_limit(self,
                                                             object market_pair)
    cdef object c_get_adjusted_limit_order_size(self,
                                                object market_pair)
    cdef double c_sum_flat_fees(self,
                                str quote_currency,
                                list flat_fees)
    cdef tuple c_get_market_making_price_and_size_limit(self,
                                                        object market_pair,
                                                        bint is_bid)
    cdef double c_calculate_effective_hedging_price(self,
                                                    OrderBook taker_order_book,
                                                    bint is_maker_bid,
                                                    double maker_order_size) except? -1
    cdef bint c_check_if_still_profitable(self,
                                          object market_pair,
                                          LimitOrder active_order,
                                          double current_hedging_price)
    cdef bint c_check_if_sufficient_balance(self,
                                            object market_pair,
                                            LimitOrder active_order)
    cdef c_check_and_create_new_orders(self,
                                       object market_pair,
                                       bint has_active_bid,
                                       bint has_active_ask)