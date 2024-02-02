from decimal import Decimal
from typing import Dict, Optional, Union

from pydantic import BaseModel

from hummingbot.smart_components.executors.arbitrage_executor.data_types import ArbitrageConfig
from hummingbot.smart_components.executors.dca_executor.data_types import DCAConfig
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.models.base import SmartComponentStatus


class ExecutorInfo(BaseModel):
    id: str
    timestamp: int
    type: str
    close_timestamp: Optional[int]
    status: SmartComponentStatus
    config: Union[PositionExecutorConfig, DCAConfig, ArbitrageConfig]
    net_pnl_pct: Decimal
    net_pnl_quote: Decimal
    cum_fees_quote: Decimal
    is_trading: bool
    custom_info: Dict  # TODO: Define the custom info type for each executor


class ExecutorHandlerInfo(BaseModel):
    controller_id: str
    status: SmartComponentStatus
    active_position_executors: list[ExecutorInfo]
    closed_position_executors: list[ExecutorInfo]
    active_dca_executors: list[ExecutorInfo]
    closed_dca_executors: list[ExecutorInfo]
    active_arbitrage_executors: list[ExecutorInfo]
    closed_arbitrage_executors: list[ExecutorInfo]
