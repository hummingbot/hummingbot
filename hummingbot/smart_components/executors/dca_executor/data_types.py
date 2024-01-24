from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.smart_components.executors.position_executor.data_types import TrailingStop
from hummingbot.smart_components.strategy_frameworks.data_types import OrderLevel


class DCAConfig(BaseModel):
    id: str
    timestamp: float
    exchange: str
    trading_pair: str
    side: TradeType
    initial_price: Decimal
    order_levels: List[OrderLevel]
    global_take_profit: Optional[Decimal] = None
    global_stop_loss: Optional[Decimal] = None
    global_trailing_stop: Optional[TrailingStop] = None
    time_limit: Optional[int] = None
    activation_threshold: Optional[Decimal] = None
    open_order_type: OrderType = OrderType.MARKET
    take_profit_order_type: OrderType = OrderType.MARKET
    stop_loss_order_type: OrderType = OrderType.MARKET
    time_limit_order_type: OrderType = OrderType.MARKET
    leverage: int = 1
