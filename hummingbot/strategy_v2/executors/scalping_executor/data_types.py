from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase


class ProfitTargetAction(BaseModel):
    percentage:Optional[Decimal]
    stop_loss_factor:Optional[Decimal]
    taker_fee_percentage:Optional[Decimal]
    maker_fee_percentage:Optional[Decimal]
    tp_price:Decimal
    action:str=None
    

class TrailingStop(BaseModel):
    activation_price: Decimal
    trailing_delta: Decimal

class TripleBarrierConfig(BaseModel):
    stop_loss_price: Decimal
    take_profit_price: Optional[Decimal]
    open_order_price: Decimal
    time_limit: Optional[int]
    open_order_type: OrderType = OrderType.LIMIT
    take_profit_order_type: OrderType = OrderType.LIMIT
    stop_loss_order_type: OrderType = OrderType.MARKET
    stop_loss_in_open_order: bool = True
    trailing_stop: Optional[TrailingStop]

class ScalpingBoundExecutorConfig(ExecutorConfigBase):
    type = "scalping_executor"
    trading_pair: str
    connector_name: str
    side: TradeType
    stop_price: Decimal
    upper_bound: Decimal
    lower_bound: Decimal
    max_loss: Decimal
    profit_target_action: Optional[ProfitTargetAction] = None
    level_id: Optional[str] = None
    qty: Optional[Decimal] = None


class ScalpingExecutorConfig(ExecutorConfigBase):
    type = "scalping_executor"
    trading_pair: str
    connector_name: str
    side: TradeType
    amount: Decimal
    leverage: Decimal = 1
    level_id: Optional[str] = None
    triple_barrier_config: TripleBarrierConfig
    profit_target_action: Optional[ProfitTargetAction]=None
    activation_bounds: Optional[List[Decimal]] = None


