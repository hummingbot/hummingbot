# distutils: language=c++

from hummingbot.core.time_iterator cimport TimeIterator
from hummingbot.core.event.event_listener cimport EventListener

from .order_tracker cimport OrderTracker

cdef class StrategyBase(TimeIterator):
    cdef:
        set _sb_markets
        EventListener _sb_create_buy_order_listener
        EventListener _sb_create_sell_order_listener
        EventListener _sb_fill_order_listener
        EventListener _sb_fail_order_listener
        EventListener _sb_cancel_order_listener
        EventListener _sb_expire_order_listener
        EventListener _sb_complete_buy_order_listener
        EventListener _sb_complete_sell_order_listener
        EventListener _sb_complete_funding_payment_listener
        EventListener _sb_position_mode_change_success_listener
        EventListener _sb_position_mode_change_failure_listener
        EventListener _sb_range_position_liquidity_added_listener
        EventListener _sb_range_position_liquidity_removed_listener
        EventListener _sb_range_position_update_listener
        EventListener _sb_range_position_update_failure_listener
        EventListener _sb_range_position_fee_collected_listener
        EventListener _sb_range_position_closed_listener
        bint _sb_delegate_lock
        public OrderTracker _sb_order_tracker

    cdef c_add_markets(self, list markets)
    cdef c_remove_markets(self, list markets)
    cdef c_did_create_buy_order(self, object order_created_event)
    cdef c_did_create_sell_order(self, object order_created_event)
    cdef c_did_fill_order(self, object order_filled_event)
    cdef c_did_fail_order(self, object order_failed_event)
    cdef c_did_cancel_order(self, object cancelled_event)
    cdef c_did_expire_order(self, object expired_event)
    cdef c_did_complete_buy_order(self, object order_completed_event)
    cdef c_did_complete_sell_order(self, object order_completed_event)
    cdef c_did_complete_funding_payment(self, object funding_payment_completed_event)
    cdef c_did_change_position_mode_succeed(self, object position_mode_changed_event)
    cdef c_did_change_position_mode_fail(self, object position_mode_changed_event)
    cdef c_did_add_liquidity(self, object add_liquidity_event)
    cdef c_did_remove_liquidity(self, object remove_liquidity_event)
    cdef c_did_update_lp_order(self, object update_lp_event)
    cdef c_did_fail_lp_update(self, object fail_lp_update_event)
    cdef c_did_collect_fee(self, object collect_fee_event)
    cdef c_did_close_position(self, object closed_event)

    cdef c_did_fail_order_tracker(self, object order_failed_event)
    cdef c_did_cancel_order_tracker(self, object order_cancelled_event)
    cdef c_did_expire_order_tracker(self, object order_expired_event)
    cdef c_did_complete_buy_order_tracker(self, object order_completed_event)
    cdef c_did_complete_sell_order_tracker(self, object order_completed_event)

    cdef str c_buy_with_specific_market(self, object market_trading_pair_tuple, object amount, object order_type = *,
                                        object price = *, double expiration_seconds = *, position_action = *)
    cdef str c_sell_with_specific_market(self, object market_trading_pair_tuple, object amount, object order_type = *,
                                         object price = *, double expiration_seconds = *, position_action = *, )
    cdef c_cancel_order(self, object market_pair, str order_id)

    cdef c_start_tracking_limit_order(self, object market_pair, str order_id, bint is_buy, object price,
                                      object quantity)
    cdef c_stop_tracking_limit_order(self, object market_pair, str order_id)
    cdef c_start_tracking_market_order(self, object market_pair, str order_id, bint is_buy, object quantity)
    cdef c_stop_tracking_market_order(self, object market_pair, str order_id)
    cdef c_track_restored_orders(self, object market_pair)
    cdef object c_sum_flat_fees(self,
                                str quote_currency,
                                list flat_fees)
