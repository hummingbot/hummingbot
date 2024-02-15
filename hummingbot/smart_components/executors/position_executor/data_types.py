from enum import Enum
from typing import Optional

from pydantic import BaseModel
from pydantic.types import Decimal

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.smart_components.executors.data_types import ExecutorConfigBase


class TrailingStop(BaseModel):
    activation_price: Decimal
    trailing_delta: Decimal


class TripleBarrierConf(BaseModel):
    # Configure the parameters for the position
    stop_loss: Optional[Decimal]
    take_profit: Optional[Decimal]
    time_limit: Optional[int]
    trailing_stop_activation_price: Optional[Decimal]
    trailing_stop_trailing_delta: Optional[Decimal]
    # Configure the parameters for the order
    open_order_type: OrderType = OrderType.LIMIT
    take_profit_order_type: OrderType = OrderType.MARKET
    stop_loss_order_type: OrderType = OrderType.MARKET
    time_limit_order_type: OrderType = OrderType.MARKET


class PositionExecutorConfig(ExecutorConfigBase):
    type = "position_executor"
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
    level_id: Optional[str] = None


class PositionExecutorStatus(Enum):
    NOT_STARTED = 1
    ACTIVE_POSITION = 2
    COMPLETED = 3
