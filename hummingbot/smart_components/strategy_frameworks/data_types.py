from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, validator

from hummingbot.core.data_type.common import OrderType, TradeType


class ExecutorHandlerStatus(Enum):
    NOT_STARTED = 1
    ACTIVE = 2
    TERMINATED = 3


class ControllerMode(Enum):
    BACKTEST = 1
    LIVE = 2


class TripleBarrierConf(BaseModel):
    # Configure the parameters for the position
    stop_loss: Optional[Decimal]
    take_profit: Optional[Decimal]
    time_limit: Optional[int]
    trailing_stop_activation_price_delta: Optional[Decimal]
    trailing_stop_trailing_delta: Optional[Decimal]
    # Configure the parameters for the order
    open_order_type: OrderType = OrderType.LIMIT
    take_profit_order_type: OrderType = OrderType.MARKET
    stop_loss_order_type: OrderType = OrderType.MARKET
    time_limit_order_type: OrderType = OrderType.MARKET

    @validator("stop_loss", "take_profit", "trailing_stop_activation_price_delta", "trailing_stop_trailing_delta",
               pre=True)
    def float_to_decimal(cls, v):
        return Decimal(v)


class OrderLevel(BaseModel):
    level: int
    side: TradeType
    order_amount_usd: Decimal
    spread_factor: Decimal = Decimal("0.0")
    order_refresh_time: int = 60
    cooldown_time: int = 0
    triple_barrier_conf: TripleBarrierConf

    @property
    def level_id(self):
        return f"{self.side.name}_{self.level}"

    @validator("order_amount_usd", "spread_factor", pre=True)
    def float_to_decimal(cls, v):
        return Decimal(v)
