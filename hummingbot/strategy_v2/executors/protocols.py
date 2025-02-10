from typing import Protocol, TypeVar, runtime_checkable

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.executor_base import ExecutorUpdateBase

ConfigT = TypeVar("ConfigT", bound="ExecutorConfigFactoryProtocol")
ExecutorT = TypeVar("ExecutorT", bound="ExecutorBaseFactoryProtocol")
StrategyT = TypeVar("StrategyT", bound=ScriptStrategyBase)
UpdateT = TypeVar("UpdateT", bound=ExecutorUpdateBase)


@runtime_checkable
class ExecutorConstructor(Protocol[StrategyT, ConfigT, ExecutorT]):
    """
    Protocol for an executor class constructor.

    It defines the __call__ signature that a class must support when used as a constructor.
    """

    def __call__(self, strategy: StrategyT, config: ConfigT, update_interval: float) -> ExecutorT:
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
