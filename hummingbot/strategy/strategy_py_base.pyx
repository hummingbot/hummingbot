from typing import List
from hummingbot.strategy.strategy_base cimport StrategyBase
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.clock import Clock

from .order_tracker import OrderTracker

cdef class StrategyPyBase(StrategyBase):
    def __init__(self):
        super().__init__()

    @property
    def order_tracker(self) -> OrderTracker:
        return self._sb_order_tracker

    def add_markets(self, markets: List[ConnectorBase]):
        self.c_add_markets(markets)

    def start(self, clock: Clock, timestamp: float):
        StrategyBase.c_start(self, clock, timestamp)

    cdef c_tick(self, double timestamp):
        StrategyBase.c_tick(self, timestamp)
        self.tick(timestamp)

    def tick(self, timestamp: float):
        raise NotImplementedError

    def stop(self, clock: Clock):
        StrategyBase.c_stop(self, clock)

    cdef c_did_create_buy_order(self, object order_created_event):
        self.did_create_buy_order(order_created_event)

    def did_create_buy_order(self, order_created_event):
        pass

    cdef c_did_create_sell_order(self, object order_created_event):
        self.did_create_sell_order(order_created_event)

    def did_create_sell_order(self, order_created_event):
        pass

    cdef c_did_fill_order(self, object order_filled_event):
        self.did_fill_order(order_filled_event)

    def did_fill_order(self, order_filled_event):
        pass

    cdef c_did_fail_order(self, object order_failed_event):
        self.did_fail_order(order_failed_event)

    def did_fail_order(self, order_failed_event):
        pass

    cdef c_did_cancel_order(self, object cancelled_event):
        self.did_cancel_order(cancelled_event)

    def did_cancel_order(self, cancelled_event):
        pass

    cdef c_did_expire_order(self, object expired_event):
        self.did_expire_order(expired_event)

    def did_expire_order(self, expired_event):
        pass

    cdef c_did_complete_buy_order(self, object order_completed_event):
        self.did_complete_buy_order(order_completed_event)

    def did_complete_buy_order(self, order_completed_event):
        pass

    cdef c_did_complete_sell_order(self, object order_completed_event):
        self.did_complete_sell_order(order_completed_event)

    def did_complete_sell_order(self, order_completed_event):
        pass
