from decimal import Decimal
import time

from hummingbot.core.event.events import TradeType
from hummingbot.strategy.triangular_arbitrage.order_tracking.order_state import OrderState


class Order:
    def __init__(self,
                 trading_pair: str,
                 id: str,
                 price: Decimal,
                 amount: Decimal,
                 side: TradeType,
                 state: OrderState = OrderState.UNSENT,
                 previously_filled: Decimal = Decimal('0'),
                 is_all_in: bool = False):
        self.id = id
        self.amount_remaining: Decimal = amount
        self.amount: Decimal = amount
        self.state = state
        self.trading_pair = trading_pair
        self._price = price
        self._side = side
        self.last_cancelled = 0.0
        self.original_cancellation = 0.0
        self._time_conceived = time.time()
        self._time_activated = float('inf')
        self.previously_filled = previously_filled
        self.is_all_in = is_all_in

    @property
    def side(self):
        return self._side

    @property
    def trade_type(self):
        return self._side

    @property
    def price(self) -> Decimal:
        return self._price

    @property
    def total(self) -> Decimal:
        return self._price * self.amount_remaining

    @property
    def time_activated(self):
        return self._time_activated

    @property
    def time_conceived(self):
        return self._time_conceived

    def update_order_id(self, order_id):
        self.id = order_id

    def is_live_uncancelled(self) -> bool:
        return self.state in [OrderState.ACTIVE, OrderState.PENDING]

    def is_live(self) -> bool:
        return self.state in [OrderState.ACTIVE, OrderState.PENDING, OrderState.PENDING_CANCEL]

    def mark_canceled(self):
        now = time.time()
        if self.state in [OrderState.ACTIVE, OrderState.PENDING, OrderState.UNSENT]:
            self.state = OrderState.PENDING_CANCEL
            self.original_cancellation = now
        self.last_cancelled = now

    def mark_active(self):
        now = time.time()
        if self.state == OrderState.HANGING:
            self.state = OrderState.PENDING_PARTIAL_TO_FULL
        else:
            self.state = OrderState.ACTIVE
        self._time_activated = now

    def __repr__(self):
        return f"(id={self.id}, price={self.price}, amount_remaining={self.amount_remaining}, state={self.state}, side={self.side})"
