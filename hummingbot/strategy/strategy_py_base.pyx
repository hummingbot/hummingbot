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

    cdef c_did_create_range_position_order(self, object order_created_event):
        self.did_create_range_position_order(order_created_event)

    def did_create_range_position_order(self, order_created_event):
        pass

    cdef c_did_remove_range_position_order(self, object order_completed_event):
        self.did_remove_range_position_order(order_completed_event)

    def did_remove_range_position_order(self, order_completed_event):
        pass
