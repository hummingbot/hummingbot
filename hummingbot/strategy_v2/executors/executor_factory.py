from typing import Any, Callable, Type, TypeVar

from hummingbot.strategy_v2.executors.protocols import ExecutorBaseFactoryProtocol, ExecutorConfigFactoryProtocol

# Type variables bound to the protocols
ConfigT = TypeVar("ConfigT", bound=ExecutorConfigFactoryProtocol)
ExecutorT = TypeVar("ExecutorT", bound=ExecutorBaseFactoryProtocol)


class ExecutorFactory:
    """
    Factory class for creating executor instances from configuration objects.

    This factory uses a registration mechanism to map ExecutorConfigFactoryProtocol types
    to concrete ExecutorBaseFactoryProtocol classes.
    """
    _registry: dict[Type[ExecutorConfigFactoryProtocol], Type[ExecutorBaseFactoryProtocol]] = {}

    @classmethod
    def register_executor(
            cls,
            config_type: Type[ExecutorConfigFactoryProtocol]
    ) -> Callable[[Type[ExecutorBaseFactoryProtocol]], Type[ExecutorBaseFactoryProtocol]]:
        """
        Decorator to register an executor class for a given executor configuration type.

        :param config_type: The type of ExecutorConfigFactoryProtocol.
        :return: A decorator that registers the executor class.
        :raises ValueError: If the executor class is already registered for the configuration type.
        :raises ValueError: If the executor class does not inherit from ExecutorBaseFactoryProtocol.
        """

        def decorator(executor_cls: Type[ExecutorBaseFactoryProtocol]) -> Type[ExecutorBaseFactoryProtocol]:
            if config_type in cls._registry:
                raise ValueError(f"Executor class already registered for config type: {config_type}")
            cls._registry[config_type] = executor_cls
            return executor_cls

        return decorator

    @classmethod
    def create_executor(
            cls, strategy: Any, config: ExecutorConfigFactoryProtocol, update_interval: float
    ) -> ExecutorBaseFactoryProtocol:
        """
        Create an executor instance based on the provided configuration.

        :param strategy: The strategy instance.
        :param config: The executor configuration.
        :param update_interval: The update interval for the executor.
        :return: An instance of ExecutorBaseFactoryProtocol.
        :raises ValueError: If the configuration type is not registered.
        """
        executor_cls = cls._registry.get(type(config))
        if executor_cls is None:
            raise ValueError(f"Unsupported executor config type: {type(config)}")
        return executor_cls(strategy, config, update_interval)
