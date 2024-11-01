from decimal import Decimal
from typing import Dict, Optional, Union

from pydantic import BaseModel

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.strategy_v2.executors.twap_executor.data_types import TWAPExecutorConfig
from hummingbot.strategy_v2.executors.xemm_executor.data_types import XEMMExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType


class ExecutorInfo(BaseModel):
    id: str
    timestamp: float
    type: str
    close_timestamp: Optional[float]
    close_type: Optional[CloseType]
    status: RunnableStatus
    config: Union[PositionExecutorConfig, XEMMExecutorConfig, ArbitrageExecutorConfig, DCAExecutorConfig, TWAPExecutorConfig, ExecutorConfigBase]
    net_pnl_pct: Decimal
    net_pnl_quote: Decimal
    cum_fees_quote: Decimal
    filled_amount_quote: Decimal
    is_active: bool
    is_trading: bool
    custom_info: Dict  # TODO: Define the custom info type for each executor
    controller_id: Optional[str] = None

    @property
    def is_done(self):
        return self.status in [RunnableStatus.TERMINATED]

    @property
    def side(self) -> Optional[TradeType]:
        return self.custom_info.get("side", None)

    @property
    def trading_pair(self) -> Optional[str]:
        return self.config.trading_pair

    @property
    def connector_name(self) -> Optional[str]:
        return self.config.connector_name

    def to_dict(self):
        base_dict = self.dict()
        base_dict["side"] = self.side
        return base_dict


class ExecutorHandlerInfo(BaseModel):
    controller_id: str
    timestamp: float
    status: RunnableStatus
    active_position_executors: list[ExecutorInfo]
    closed_position_executors: list[ExecutorInfo]
    active_dca_executors: list[ExecutorInfo]
    closed_dca_executors: list[ExecutorInfo]
    active_arbitrage_executors: list[ExecutorInfo]
    closed_arbitrage_executors: list[ExecutorInfo]


class PerformanceReport(BaseModel):
    realized_pnl_quote: Decimal = Decimal("0")
    unrealized_pnl_quote: Decimal = Decimal("0")
    unrealized_pnl_pct: Decimal = Decimal("0")
    realized_pnl_pct: Decimal = Decimal("0")
    global_pnl_quote: Decimal = Decimal("0")
    global_pnl_pct: Decimal = Decimal("0")
    volume_traded: Decimal = Decimal("0")
    open_order_volume: Decimal = Decimal("0")
    inventory_imbalance: Decimal = Decimal("0")
    close_type_counts: Dict[CloseType, int] = {}
