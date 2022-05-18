from hummingbot.strategy.strategy_base cimport StrategyBase
from hummingbot.core.clock import Clock
from hummingbot.core.clock cimport Clock
from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderFilledEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderExpiredEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    FundingPaymentCompletedEvent,
    PositionModeChangeEvent,
    RangePositionLiquidityAddedEvent,
    RangePositionLiquidityRemovedEvent,
    RangePositionUpdateEvent,
    RangePositionUpdateFailureEvent,
    RangePositionFeeCollectedEvent,
    RangePositionClosedEvent
)


cdef class StrategyPyBase(StrategyBase):
    def __init__(self):
        super().__init__()

    cdef c_start(self, Clock clock, double timestamp):
        StrategyBase.c_start(self, clock, timestamp)
        self.start(clock, timestamp)

    def start(self, clock: Clock, timestamp: float):
        pass

    cdef c_stop(self, Clock clock):
        StrategyBase.c_stop(self, clock)
        self.stop(clock)

    def stop(self, clock: Clock):
        pass

    cdef c_tick(self, double timestamp):
        StrategyBase.c_tick(self, timestamp)
        self.tick(timestamp)

    def tick(self, timestamp: float):
        raise NotImplementedError

    cdef c_did_create_buy_order(self, object order_created_event):
        self.did_create_buy_order(order_created_event)

    def did_create_buy_order(self, order_created_event: BuyOrderCreatedEvent):
        pass

    cdef c_did_create_sell_order(self, object order_created_event):
        self.did_create_sell_order(order_created_event)

    def did_create_sell_order(self, order_created_event: SellOrderCreatedEvent):
        pass

    cdef c_did_fill_order(self, object order_filled_event):
        self.did_fill_order(order_filled_event)

    def did_fill_order(self, order_filled_event: OrderFilledEvent):
        pass

    cdef c_did_fail_order(self, object order_failed_event):
        self.did_fail_order(order_failed_event)

    def did_fail_order(self, order_failed_event: MarketOrderFailureEvent):
        pass

    cdef c_did_cancel_order(self, object cancelled_event):
        self.did_cancel_order(cancelled_event)

    def did_cancel_order(self, cancelled_event: OrderCancelledEvent):
        pass

    cdef c_did_expire_order(self, object expired_event):
        self.did_expire_order(expired_event)

    def did_expire_order(self, expired_event: OrderExpiredEvent):
        pass

    cdef c_did_complete_buy_order(self, object order_completed_event):
        self.did_complete_buy_order(order_completed_event)

    def did_complete_buy_order(self, order_completed_event: BuyOrderCompletedEvent):
        pass

    cdef c_did_complete_sell_order(self, object order_completed_event):
        self.did_complete_sell_order(order_completed_event)

    def did_complete_sell_order(self, order_completed_event: SellOrderCompletedEvent):
        pass

    cdef c_did_complete_funding_payment(self, object funding_payment_completed_event):
        self.did_complete_funding_payment(funding_payment_completed_event)

    def did_complete_funding_payment(self, funding_payment_completed_event: FundingPaymentCompletedEvent):
        pass

    cdef c_did_change_position_mode_succeed(self, object position_mode_changed_event):
        self.did_change_position_mode_succeed(position_mode_changed_event)

    def did_change_position_mode_succeed(self, position_mode_changed_event: PositionModeChangeEvent):
        pass

    cdef c_did_change_position_mode_fail(self, object position_mode_changed_event):
        self.did_change_position_mode_fail(position_mode_changed_event)

    def did_change_position_mode_fail(self, position_mode_changed_event: PositionModeChangeEvent):
        pass

    cdef c_did_add_liquidity(self, object add_liquidity_event):
        self.did_add_liquidity(add_liquidity_event)

    def did_add_liquidity(self, add_liquidity_event: RangePositionLiquidityAddedEvent):
        pass

    cdef c_did_remove_liquidity(self, object remove_liquidity_event):
        self.did_remove_liquidity(remove_liquidity_event)

    def did_remove_liquidity(self, remove_liquidity_event: RangePositionLiquidityRemovedEvent):
        pass

    cdef c_did_update_lp_order(self, object update_lp_event):
        self.did_update_lp_order(update_lp_event)

    def did_update_lp_order(self, update_lp_event: RangePositionUpdateEvent):
        pass

    cdef c_did_fail_lp_update(self, object fail_lp_update_event):
        self.did_fail_lp_update(fail_lp_update_event)

    def did_fail_lp_update(self, fail_lp_update_event: RangePositionUpdateFailureEvent):
        pass

    cdef c_did_collect_fee(self, object collect_fee_event):
        self.did_collect_fee(collect_fee_event)

    def did_collect_fee(self, collect_fee_event: RangePositionFeeCollectedEvent):
        pass

    cdef c_did_close_position(self, object closed_position_event):
        self.did_close_position(closed_position_event)

    def did_close_position(self, closed_position_event: RangePositionClosedEvent):
        pass
