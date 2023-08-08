from enum import Enum
from typing import Optional

from pydantic import BaseModel

from hummingbot.core.data_type.common import OrderType


class MetaStrategyStatus(Enum):
    NOT_STARTED = 1
    ACTIVE = 2
    TERMINATED = 3


class MetaStrategyMode(Enum):
    BACKTEST = 1
    LIVE = 2


class OrderLevel(BaseModel):
    level: int
    side: str
    order_amount_usd: float
    spread_factor: float
    # Configure the parameters for the position
    stop_loss: Optional[float]
    take_profit: Optional[float]
    time_limit: Optional[int]
    trailing_stop_activation_delta: Optional[float]
    trailing_stop_trailing_delta: Optional[float]
    # Configure the parameters for the order
    open_order_type: OrderType = OrderType.LIMIT
    take_profit_order_type: OrderType = OrderType.MARKET
    stop_loss_order_type: OrderType = OrderType.MARKET
    time_limit_order_type: OrderType = OrderType.MARKET

    def __post_init__(self):
        self.level_id = f"{self.side}_{self.level}"
