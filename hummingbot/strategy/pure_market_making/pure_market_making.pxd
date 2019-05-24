# distutils: language=c++

from libc.stdint cimport int64_t

from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.market.market_base cimport MarketBase
from hummingbot.strategy.strategy_base cimport StrategyBase

cdef class PureMarketMakingStrategy(StrategyBase):
    cdef:
        set _markets
        set _maker_markets
        set _radar_relay_type_exchanges
        dict _market_pairs
        bint _all_markets_ready
        double _bid_place_threshold
        double _ask_place_threshold
        double _cancel_order_wait_time
        double _order_size
        double _status_report_interval
        double _last_timestamp
        double _limit_order_min_expiration
        dict _tracked_maker_orders
        dict _order_id_to_market_pair
        dict _shadow_tracked_maker_orders
        dict _shadow_order_id_to_market_pair
        dict _order_fill_buy_events
        dict _order_fill_sell_events
        dict _time_to_cancel
        object _in_flight_cancels
        object _shadow_gc_requests

        EventListener _order_filled_listener
        EventListener _buy_order_completed_listener
        EventListener _sell_order_completed_listener
        EventListener _order_failed_listener
        EventListener _order_cancelled_listener
        EventListener _order_expired_listener
        int64_t _logging_options


    cdef c_buy_with_specific_market(self, MarketBase market, str symbol, double amount,
                                    double price, object order_type = *, double expiration_seconds = *)
    cdef c_sell_with_specific_market(self, MarketBase market, str symbol, double amount,
                                    double price, object order_type = *, double expiration_seconds = *)
    cdef c_cancel_order(self, object market_pair, str order_id)
    cdef c_process_market_pair(self, object market_pair, list active_ddex_orders)
    cdef c_did_fill_order(self, object order_filled_event)
    cdef c_did_fail_order(self, object order_failed_event)
    cdef c_did_cancel_order(self, object cancelled_event)
    cdef c_did_complete_buy_order(self, object order_completed_event)
    cdef c_did_complete_sell_order(self, object order_completed_event)
    cdef c_check_and_cleanup_shadow_records(self)
    cdef c_start_tracking_order(self, object market_pair, str order_id, bint is_buy, object price, object quantity)
    cdef c_stop_tracking_order(self, object market_pair, str order_id)
    cdef bint c_check_if_sufficient_balance(self, object market_pair)
    cdef c_create_new_orders(self, object market_pair)