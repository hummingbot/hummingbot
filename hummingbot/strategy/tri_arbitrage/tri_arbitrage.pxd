# distutils: language=c++

from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t

cdef class ArbitrageStrategy(StrategyBase):
    cdef:
        list _market_pairs
        list _initialize_market_assets
        bint _all_markets_ready
        dict _order_id_to_market
        object _min_profitability
        object _maxorder_amount
        object _fee_amount
        object _max_order_size
        object _min_order_size
        double _status_report_interval
        double _last_timestamp
        dict _last_trade_timestamps
        double _next_trade_delay
        set _sell_markets
        set _buy_markets
        int64_t _logging_options
        object _exchange_rate_conversion
        int _failed_order_tolerance
        bint _cool_off_logged
        bint _use_oracle_conversion_rate
        object _secondary_to_primary_base_conversion_rate
        object _secondary_to_primary_quote_conversion_rate
        bint _hb_app_notification
        object _current_profitability
        double _last_order_logged
        double _last_pair_update_logged
        list _maker_order_ids
        int _tradeflag
        int _tradeid
        int _mpaircycle
        int _tickcount
        object _pricebuffer
        object _q1
        object _q2
        object _q3
        object _p1
        object _p2
        object _p3
        object _Trading_Dataset

    cdef tuple c_calculate_arbitrage_top_order_profitability(self, object market_pair)
    cdef c_process_market_pair(self, object market_pair)
    cdef c_process_market_pair_inner(self, object Trading_Dataset)
    cdef tuple c_find_best_profitable_amount(self, object trade_strategy)
    cdef bint c_ready_for_new_orders(self, list market_trading_pairs)
    cdef c_maketrade(self, object Trading_Dataset, tradeid,quantized_first_amount, quantized_second_amount, quantized_third_amount,p1,p2,p3,minprof)

