# distutils: language=c++

from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.strategy.strategy_base cimport StrategyBase
from libc.stdint cimport int64_t


cdef class ArbitrageStrategy(StrategyBase):
    cdef:
        list _market_pairs
        bint _all_markets_ready
        dict _order_id_to_market
        double _min_profitability
        double _max_order_size
        double _min_order_size
        double _status_report_interval
        double _last_timestamp
        dict _last_trade_timestamps
        double _next_trade_delay
        set _sell_markets
        set _buy_markets
        int64_t _logging_options
        object _exchange_rate_conversion

    cdef tuple c_calculate_arbitrage_top_order_profitability(self, object market_pair)
    cdef c_process_market_pair(self, object market_pair)
    cdef c_process_market_pair_inner(self, object buy_market_symbol_pair,object sell_market_symbol_pair)
    cdef tuple c_find_best_profitable_amount(self, object buy_market_symbol_pair, object sell_market_symbol_pair)
    cdef c_ready_for_new_orders(self, list market_symbol_pairs)


cdef list c_find_profitable_arbitrage_orders(double min_profitability,
                                             OrderBook buy_order_book,
                                             OrderBook sell_order_book,
                                             str buy_market_quote_currency,
                                             str sell_market_quote_currency)
