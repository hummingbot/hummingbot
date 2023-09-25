from enum import Enum
from typing import Optional

from pydantic import BaseModel
from pydantic.types import Decimal

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder


class TrailingStop(BaseModel):
    activation_price_delta: Decimal
    trailing_delta: Decimal


class PositionConfig(BaseModel):
    timestamp: float
    trading_pair: str
    exchange: str
    side: TradeType
    amount: Decimal
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    trailing_stop: Optional[TrailingStop] = None
    time_limit: Optional[int] = None
    entry_price: Optional[Decimal] = None
    open_order_type: OrderType = OrderType.MARKET
    take_profit_order_type: OrderType = OrderType.MARKET
    stop_loss_order_type: OrderType = OrderType.MARKET
    time_limit_order_type: OrderType = OrderType.MARKET
    leverage: int = 1


class PositionExecutorStatus(Enum):
    NOT_STARTED = 1
    ACTIVE_POSITION = 2
    COMPLETED = 3


class CloseType(Enum):
    TIME_LIMIT = 1
    STOP_LOSS = 2
    TAKE_PROFIT = 3
    EXPIRED = 4
    EARLY_STOP = 5
    TRAILING_STOP = 6
    INSUFFICIENT_BALANCE = 7


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
