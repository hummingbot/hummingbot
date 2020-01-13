# distutils: language=c++

from libc.stdint cimport int64_t

from hummingbot.strategy.strategy_base cimport StrategyBase
from hummingbot.core.data_type.order_book cimport OrderBook

from .order_filter_delegate cimport OrderFilterDelegate
from .order_pricing_delegate cimport OrderPricingDelegate
from .order_sizing_delegate cimport OrderSizingDelegate
from .asset_price_delegate cimport AssetPriceDelegate


cdef class PureMarketMakingStrategyV2(StrategyBase):
    cdef:
        dict _market_infos
        bint _all_markets_ready
        bint _enable_order_filled_stop_cancellation
        bint _best_bid_ask_jump_mode
        bint _add_transaction_costs_to_orders

        double _cancel_order_wait_time
        double _expiration_seconds
        double _status_report_interval
        double _last_timestamp
        double _filled_order_replenish_wait_time
        object _best_bid_ask_jump_orders_depth

        dict _time_to_cancel

        int64_t _logging_options

        OrderFilterDelegate _filter_delegate
        OrderPricingDelegate _pricing_delegate
        OrderSizingDelegate _sizing_delegate
        AssetPriceDelegate _asset_price_delegate

    cdef object c_get_orders_proposal_for_market_info(self,
                                                      object market_info,
                                                      list active_maker_orders)
    cdef c_execute_orders_proposal(self,
                                   object market_info,
                                   object orders_proposal)
    cdef object c_get_penny_jumped_pricing_proposal(self,
                                                    object market_info,
                                                    object pricing_proposal,
                                                    list active_orders)
    cdef tuple c_check_and_add_transaction_costs_to_pricing_proposal(self,
                                                                     object market_info,
                                                                     object pricing_proposal,
                                                                     object sizing_proposal)
    cdef object c_filter_orders_proposal_for_takers(self, object market_info, object orders_proposal)
