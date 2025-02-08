from typing import Any, Type

from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase


class ExecutorFactory:
    """
    Factory class for creating executor instances from configuration objects.

    This factory uses a registration mechanism to map ExecutorConfigBase types
    to concrete ExecutorBase classes.
    """
    _registry: dict[Type[ExecutorConfigBase], Type[ExecutorBase]] = {}

    @classmethod
    def register_executor(cls, config_type: Type[ExecutorConfigBase]) -> Any:
        """
        Decorator to register an executor class for a given executor configuration type.

        :param config_type: The type of ExecutorConfigBase.
        :return: A decorator that registers the executor class.
        """
        def decorator(executor_cls: Type[ExecutorBase]) -> Type[ExecutorBase]:
            cls._registry[config_type] = executor_cls
            return executor_cls
        return decorator

    @classmethod
    def create_executor(
        cls, strategy: Any, config: ExecutorConfigBase, update_interval: float
    ) -> ExecutorBase:
        """
        Create an executor instance based on the provided configuration.

        :param strategy: The strategy instance.
        :param config: The executor configuration.
        :param update_interval: The update interval for the executor.
        :return: An instance of ExecutorBase.
        :raises ValueError: If the configuration type is not registered.
        """
        executor_cls = cls._registry.get(type(config))
        if executor_cls is None:
            raise ValueError(f"Unsupported executor config type: {type(config)}")
        return executor_cls(strategy, config, update_interval)
