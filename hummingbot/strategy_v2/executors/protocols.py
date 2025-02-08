from typing import Any, Protocol, TypeVar, runtime_checkable


@runtime_checkable
class ExecutorConfigFactoryProtocol(Protocol):
    """
    Protocol for an executor configuration as it relates to the ExecutorFactory.

    :ivar id: Unique identifier for the configuration.
    :ivar controller_id: Optional identifier for the controller.
    """
    id: str
    controller_id: str | None


T = TypeVar("T", bound="ExecutorBaseFactoryProtocol")


@runtime_checkable
class ExecutorConstructor(Protocol[T]):
    """
    Protocol for an executor class constructor.

    It defines the __call__ signature that a class must support when used as a constructor.
    """

    def __call__(self, strategy: Any, config: ExecutorConfigFactoryProtocol, update_interval: float) -> T:
        ...


@runtime_checkable
class ExecutorBaseFactoryProtocol(Protocol):
    """
    Protocol for an executor instance as it relates to the ExecutorFactory.

    :ivar config: The executor configuration.
    """
    config: ExecutorConfigFactoryProtocol

    def __init__(self, strategy: Any, config: ExecutorConfigFactoryProtocol, update_interval: float) -> None:
        ...

    def start(self) -> None:
        """
        Start the executor.
        """
        ...
