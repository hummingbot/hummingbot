from decimal import Decimal
from typing import Counter, Dict, Optional, Union

from pydantic import BaseModel

from hummingbot.core.data_type.common import TradeType
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
    is_active: bool
    is_trading: bool
    custom_info: Dict  # TODO: Define the custom info type for each executor
    controller_id: Optional[str] = None

    @property
    def side(self) -> Optional[TradeType]:
        return self.custom_info.get("side", None)

    @property
    def trading_pair(self) -> Optional[str]:
        return self.config.trading_pair

    @property
    def connector_name(self) -> Optional[str]:
        return self.config.connector_name


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


class PerformanceReport(BaseModel):
    realized_pnl_quote: Decimal
    unrealized_pnl_quote: Decimal
    unrealized_pnl_pct: Decimal
    realized_pnl_pct: Decimal
    global_pnl_quote: Decimal
    global_pnl_pct: Decimal
    volume_traded: Decimal
    close_type_counts: Counter[CloseType]
