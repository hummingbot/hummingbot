# distutils: language=c++

from hummingbot.strategy.strategy_base cimport StrategyBase
from hummingbot.market.market_base cimport MarketBase
from libc.stdint cimport int64_t

cdef class HelloWorldStrategy(StrategyBase):
    cdef:
        list _market_pairs
        double _target_amount
        double _target_profitability
        int64_t _logging_options
        double _status_report_interval
        double _refetch_market_info_interval
        bint _all_markets_ready
        double _last_timestamp
        set _markets
        object strategy
        dict _market_info
        set _matching_pairs
        list _target_symbols
        list _equivalent_token
        dict _equivalent_token_dict
        str _discovery_method
        list _fetch_market_info_task_list

    cdef c_process_market(self, object market_info)
    cdef c_tick(self, double timestamp)
    cdef c_buy_with_specific_market(self, MarketBase market, str symbol, double amount,
                                    object order_type = *, double price = *)
    cdef c_sell_with_specific_market(self, MarketBase market, str symbol, double amount,
                                    object order_type = *, double price = *)
    cdef c_cancel_order(self, object market_info, str order_id)
    cdef c_did_fill_order(self, object order_filled_event)
    cdef c_did_fail_order(self, object order_failed_event)
    cdef c_did_cancel_order(self, object cancelled_event)
    cdef c_did_complete_buy_order(self, object order_completed_event)
    cdef c_did_complete_sell_order(self, object order_completed_event)
    cdef c_place_orders(self, object market_info)
    cdef c_has_enough_balance(self, object market_info)
    cdef c_process_market(self, object market_info)
