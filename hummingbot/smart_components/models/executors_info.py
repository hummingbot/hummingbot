from decimal import Decimal
from typing import Dict, Optional, Union

from pydantic import BaseModel

from hummingbot.smart_components.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.smart_components.executors.data_types import ExecutorConfigBase
from hummingbot.smart_components.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.models.executors import CloseType


class ExecutorInfo(BaseModel):
    id: str
    timestamp: float
    type: str
    close_timestamp: Optional[int]
    close_type: Optional[CloseType]
    status: SmartComponentStatus
    config: Union[PositionExecutorConfig, ArbitrageExecutorConfig, DCAExecutorConfig, ExecutorConfigBase]
    net_pnl_pct: Decimal
    net_pnl_quote: Decimal
    cum_fees_quote: Decimal
    filled_amount_quote: Decimal
    is_trading: bool
    custom_info: Dict  # TODO: Define the custom info type for each executor


class ExecutorHandlerInfo(BaseModel):
    controller_id: str
    timestamp: float
    status: SmartComponentStatus
    active_position_executors: list[ExecutorInfo]
    closed_position_executors: list[ExecutorInfo]
    active_dca_executors: list[ExecutorInfo]
    closed_dca_executors: list[ExecutorInfo]
    active_arbitrage_executors: list[ExecutorInfo]
    closed_arbitrage_executors: list[ExecutorInfo]
