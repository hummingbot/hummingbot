from enum import Enum
from typing import Optional

from pydantic import BaseModel
from pydantic.types import Decimal

from hummingbot.core.data_type.common import OrderType, PositionSide
from hummingbot.core.data_type.in_flight_order import InFlightOrder


class PositionConfig(BaseModel):
    timestamp: float
    trading_pair: str
    exchange: str
    order_type: OrderType
    side: PositionSide
    entry_price: Optional[Decimal] = None
    amount: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    time_limit: int


class PositionExecutorStatus(Enum):
    NOT_STARTED = 1
    ORDER_PLACED = 2
    CANCELED_BY_TIME_LIMIT = 3
    ACTIVE_POSITION = 4
    CLOSE_PLACED = 5
    CLOSED_BY_TIME_LIMIT = 6
    CLOSED_BY_STOP_LOSS = 7
    CLOSED_BY_TAKE_PROFIT = 8


class TrackedOrder:
    def __init__(self, order_id: Optional[str] = None):
        self._order_id = order_id
        self._order = None

    @property
    def order_id(self):
        return self._order_id

    @order_id.setter
    def order_id(self, order_id: str):
        self._order_id = order_id

    @property
    def order(self):
        return self._order

    @order.setter
    def order(self, order: InFlightOrder):
        self._order = order

    @property
    def average_executed_price(self):
        if self.order:
            return self.order.average_executed_price
        else:
            return None

    @property
    def executed_amount_base(self):
        if self.order:
            return self.order.executed_amount_base
        else:
            return Decimal("0")

    @property
    def cum_fees(self):
        if self.order:
            return self.order.cumulative_fee_paid(token=self.order.quote_asset)
        else:
            return Decimal("0")
