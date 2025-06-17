from decimal import Decimal
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig
from hummingbot.strategy_v2.executors.order_executor.data_types import OrderExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.strategy_v2.executors.twap_executor.data_types import TWAPExecutorConfig
from hummingbot.strategy_v2.executors.xemm_executor.data_types import XEMMExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType

AnyExecutorConfig = Union[PositionExecutorConfig, DCAExecutorConfig, GridExecutorConfig, XEMMExecutorConfig, ArbitrageExecutorConfig, OrderExecutorConfig, TWAPExecutorConfig]


class ExecutorInfo(BaseModel):
    id: str
    timestamp: float
    type: str
    status: RunnableStatus
    config: AnyExecutorConfig = Field(..., discriminator="type")
    net_pnl_pct: Decimal
    net_pnl_quote: Decimal
    cum_fees_quote: Decimal
    filled_amount_quote: Decimal
    is_active: bool
    is_trading: bool
    custom_info: Dict
    close_timestamp: Optional[float] = None
    close_type: Optional[CloseType] = None
    controller_id: Optional[str] = None
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def is_done(self):
        return self.status == RunnableStatus.TERMINATED

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
        base_dict = self.model_dump()
        base_dict["side"] = self.side
        return base_dict


class PerformanceReport(BaseModel):
    realized_pnl_quote: Decimal = Decimal("0")
    unrealized_pnl_quote: Decimal = Decimal("0")
    unrealized_pnl_pct: Decimal = Decimal("0")
    realized_pnl_pct: Decimal = Decimal("0")
    global_pnl_quote: Decimal = Decimal("0")
    global_pnl_pct: Decimal = Decimal("0")
    volume_traded: Decimal = Decimal("0")
    positions_summary: List = []
    close_type_counts: Dict[CloseType, int] = {}
