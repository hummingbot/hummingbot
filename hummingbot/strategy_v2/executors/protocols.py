from decimal import Decimal
from typing import Protocol, TypeVar, runtime_checkable

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.models.base import RunnableStatus

ConfigT = TypeVar("ConfigT", bound="ExecutorConfigFactoryProtocol")
ExecutorT = TypeVar("ExecutorT", bound="ExecutorBaseFactoryProtocol")
ExecutorInfoT = TypeVar("ExecutorInfoT", bound="ExecutorBaseInfoProtocol")
StrategyT = TypeVar("StrategyT", bound=ScriptStrategyBase)
UpdateT = TypeVar("UpdateT", bound="ExecutorUpdateFactoryProtocol")
CustomInfoT = TypeVar('CustomInfoT', bound="ExecutorCustomInfoFactoryProtocol")


@runtime_checkable
class ExecutorCustomInfoFactoryProtocol(Protocol[ExecutorInfoT]):
    """Base protocol for executor custom info"""
    side: TradeType | None

    def __init__(self, executor: ExecutorInfoT) -> None:
        ...


@runtime_checkable
class ExecutorUpdateFactoryProtocol(Protocol):
    """Base protocol for executor updates"""

    def validate(self) -> bool:
        """Validate update parameters"""
        ...


@runtime_checkable
class ExecutorConfigFactoryProtocol(Protocol):
    """
    Protocol for an executor configuration as it relates to the ExecutorFactory.

    :ivar id: Unique identifier for the configuration.
    :ivar controller_id: Optional identifier for the controller.
    """
    id: str
    controller_id: str | None


@runtime_checkable
class ExecutorConfigInfoProtocol(ExecutorConfigFactoryProtocol, Protocol):
    """
    Protocol for an executor configuration as it relates to the ExecutorInfo.

    :ivar id: Unique identifier for the configuration.
    :ivar controller_id: Optional identifier for the controller.
    :ivar trading_pair: The trading pair for the configuration.
    :ivar connector_name: The connector name for the configuration.
    """
    type: str
    side: TradeType
    timestamp: float
    trading_pair: str
    connector_name: str


@runtime_checkable
class ExecutorBaseFactoryProtocol(Protocol):
    """
    Protocol for an executor instance as it relates to the ExecutorFactory.

    :ivar config: The executor configuration.
    """
    config: ExecutorConfigFactoryProtocol

    def __init__(self, strategy: StrategyT, config: ConfigT, update_interval: float) -> None:
        ...

    def start(self) -> None:
        """
        Start the executor.
        """
        ...

    def update_live(self, update_data: UpdateT) -> None:
        """Update executor with live data."""
        ...


@runtime_checkable
class ExecutorBaseInfoProtocol(Protocol):
    """
    Protocol for an executor instance as it relates to the ExecutorInfo.

    :ivar config: The executor configuration.
    :ivar status: The status of the executor.
    :ivar is_active: Whether the executor is active.
    :ivar is_trading: Whether the executor is trading.
    :ivar net_pnl_pct: The net profit/loss percentage.
    :ivar net_pnl_quote: The net profit/loss in quote currency.
    """
    config: ExecutorConfigInfoProtocol
    status: RunnableStatus
    is_active: bool
    is_trading: bool
    net_pnl_pct: Decimal
    net_pnl_quote: Decimal
    cum_fees_quote: Decimal
    filled_amount_quote: Decimal
