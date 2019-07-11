# distutils: language=c++

from libc.stdint cimport int64_t

from hummingbot.market.market_base cimport MarketBase
from hummingbot.strategy.strategy_base cimport StrategyBase

from .order_filter_delegate cimport OrderFilterDelegate
from .order_pricing_delegate cimport OrderPricingDelegate
from .order_sizing_delegate cimport OrderSizingDelegate


cdef class PureMarketMakingStrategyV2(StrategyBase):
    cdef:
        dict _market_infos
        bint _all_markets_ready
        double _cancel_order_wait_time
        double _status_report_interval
        double _last_timestamp
        double _limit_order_min_expiration
        dict _tracked_maker_orders
        dict _order_id_to_market_info
        dict _shadow_tracked_maker_orders
        dict _shadow_order_id_to_market_info
        dict _time_to_cancel
        object _in_flight_cancels
        object _shadow_gc_requests

        int64_t _logging_options

        OrderFilterDelegate _filter_delegate
        OrderPricingDelegate _pricing_delegate
        OrderSizingDelegate _sizing_delegate
        bint _delegate_lock

    cdef c_buy_with_specific_market(self, MarketBase market, str symbol, double amount,
                                    double price, object order_type = *, double expiration_seconds = *)
    cdef c_sell_with_specific_market(self, MarketBase market, str symbol, double amount,
                                    double price, object order_type = *, double expiration_seconds = *)
    cdef c_cancel_order(self, object market_info, str order_id)
    cdef object c_get_orders_proposal_for_market_info(self, object market_info, list active_maker_orders)
    cdef c_check_and_cleanup_shadow_records(self)
    cdef c_start_tracking_order(self, object market_info, str order_id, bint is_buy, object price, object quantity)
    cdef c_stop_tracking_order(self, object market_info, str order_id)
    cdef c_execute_orders_proposal(self, object market_info, object orders_proposal)
