from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.executor_factory import ExecutorFactory
from hummingbot.strategy_v2.executors.protocols import ExecutorBaseInfoProtocol, ExecutorCustomInfoFactoryProtocol
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType


class ExecutorCustomInfoBase(ExecutorCustomInfoFactoryProtocol):
    """Implementation of the default executor custom info"""
    def __init__(self, executor: ExecutorBaseInfoProtocol):
        self.side = executor.config.side


class ExecutorInfo(BaseModel):
    """
    Information about an executor instance that is configuration-agnostic.

    This class provides a standardized way to represent executor state and performance
    without coupling to specific executor implementations.
    """
    # Core identification
    id: str = Field(..., description="Unique identifier for this executor instance")
    type: str = Field(..., description="Type identifier for the executor")
    controller_id: Optional[str] = Field(None, description="ID of the controlling strategy")

    # Timing information
    timestamp: float = Field(..., description="Creation timestamp")
    close_timestamp: Optional[float] = Field(None, description="Timestamp when executor was closed")

    # Market information
    trading_pair: str = Field(..., description="Trading pair being executed")
    connector_name: str = Field(..., description="Name of the exchange connector")

    # Status information
    status: RunnableStatus = Field(..., description="Current executor status")
    close_type: Optional[CloseType] = Field(None, description="How the executor was closed")
    is_active: bool = Field(..., description="Whether the executor is currently active")
    is_trading: bool = Field(..., description="Whether the executor is actively trading")

    # Performance metrics
    net_pnl_pct: Decimal = Field(default=Decimal("0"), description="Net profit/loss percentage")
    net_pnl_quote: Decimal = Field(default=Decimal("0"), description="Net profit/loss in quote currency")
    cum_fees_quote: Decimal = Field(default=Decimal("0"), description="Cumulative fees paid in quote currency")
    filled_amount_quote: Decimal = Field(default=Decimal("0"), description="Total filled amount in quote currency")

    # Extensibility
    custom_info: ExecutorCustomInfoFactoryProtocol = Field(default_factory=ExecutorCustomInfoBase,
                                                           description="Implementation-specific information")

    class Config:
        """Pydantic config"""
        arbitrary_types_allowed = True
        json_encoders = {
            Decimal: str,
        }

    @property
    def is_done(self) -> bool:
        """Whether the executor has completed its execution"""
        return self.status in [RunnableStatus.TERMINATED]

    @property
    def side(self) -> Optional[TradeType]:
        """Trading side if applicable"""
        return self.custom_info.side

    def to_dict(self) -> Dict:
        """Convert to dictionary representation"""
        base_dict = self.dict()
        base_dict["side"] = self.side

        # Convert timestamps to ISO format
        # if base_dict["timestamp"]:
        #     base_dict["timestamp"] = datetime.fromtimestamp(base_dict["timestamp"]).isoformat()
        # if base_dict["close_timestamp"]:
        #     base_dict["close_timestamp"] = datetime.fromtimestamp(base_dict["close_timestamp"]).isoformat()

        # Handle NaN values
        # for field in ["net_pnl_quote", "net_pnl_pct", "cum_fees_quote", "filled_amount_quote"]:
        #     if field in base_dict and isinstance(base_dict[field], Decimal) and base_dict[field].is_nan():
        #         base_dict[field] = "0"
        #     elif field in base_dict and isinstance(base_dict[field], Decimal):
        #         base_dict[field] = str(base_dict[field])

        return base_dict

    @classmethod
    def from_executor(cls, executor: ExecutorBaseInfoProtocol) -> "ExecutorInfo":
        """
        Create ExecutorInfo from an executor instance.

        :param executor: The executor instance.
        :return: An instance of ExecutorInfo.
        """
        return cls(
            id=executor.config.id,
            type=executor.config.type,
            controller_id=executor.config.controller_id,
            timestamp=executor.config.timestamp,
            trading_pair=executor.config.trading_pair,
            connector_name=executor.config.connector_name,
            status=executor.status,
            close_type=executor.close_type if hasattr(executor, "close_type") else None,
            close_timestamp=executor.close_timestamp if hasattr(executor, "close_timestamp") else None,
            is_active=executor.is_active,
            is_trading=executor.is_trading,
            net_pnl_pct=executor.net_pnl_pct,
            net_pnl_quote=executor.net_pnl_quote,
            cum_fees_quote=executor.cum_fees_quote,
            filled_amount_quote=executor.filled_amount_quote,
            custom_info=ExecutorFactory.get_custom_info(executor),
        )


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
    positions_summary: List = []
    close_type_counts: Dict[CloseType, int] = {}
