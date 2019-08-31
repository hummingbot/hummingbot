# distutils: language=c++

from libc.stdint cimport int64_t

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

        dict _time_to_cancel

        int64_t _logging_options

        OrderFilterDelegate _filter_delegate
        OrderPricingDelegate _pricing_delegate
        OrderSizingDelegate _sizing_delegate

    cdef object c_get_orders_proposal_for_market_info(self, object market_info, list active_maker_orders)
    cdef c_execute_orders_proposal(self, object market_info, object orders_proposal)
