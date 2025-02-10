import inspect
from typing import Callable, Type

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.executor_base import ExecutorUpdateBase
from hummingbot.strategy_v2.executors.protocols import ExecutorBaseFactoryProtocol, ExecutorConfigFactoryProtocol


class ExecutorFactory:
    """
    Factory class for creating executor instances from configuration objects.

    This factory uses a registration mechanism to map ExecutorConfigFactoryProtocol types
    to concrete ExecutorBaseFactoryProtocol classes.
    """
    _registry: dict[Type[ExecutorConfigFactoryProtocol], Type[ExecutorBaseFactoryProtocol]] = {}
    _update_types: dict[Type[ExecutorConfigFactoryProtocol], Type[ExecutorUpdateBase]] = {}
    _executor_ids: dict[Type[ExecutorConfigFactoryProtocol], set[str]] = {}

    @classmethod
    def register_executor(
            cls,
            config_type: Type[ExecutorConfigFactoryProtocol],
            update_type: Type[ExecutorUpdateBase] | None = None,
    ) -> Callable[[Type[ExecutorBaseFactoryProtocol]], Type[ExecutorBaseFactoryProtocol]]:
        """
        Decorator to register an executor class for a given executor configuration type.

        :param config_type: The type of ExecutorConfigFactoryProtocol.
        :param update_type: The type of ExecutorUpdateFactoryProtocol.
        :return: A decorator that registers the executor class.
        :raises ValueError: If the executor class is already registered for the configuration type.
        :raises ValueError: If the executor class does not inherit from ExecutorBaseFactoryProtocol.
        """

        def decorator(executor_cls: Type[ExecutorBaseFactoryProtocol]) -> Type[ExecutorBaseFactoryProtocol]:
            # Check that config_type is not an abstract or protocol-only type.
            if inspect.isabstract(config_type) or inspect.isclass(config_type) and getattr(config_type, "__is_protocol__", False):
                raise ValueError("config_type must be a concrete class, not just a protocol")
            if config_type in cls._registry:
                raise ValueError(f"Executor class already registered for config type: {config_type}")
            cls._registry[config_type] = executor_cls
            if update_type is not None:
                cls._update_types[config_type] = update_type
            return executor_cls
        return decorator

    @classmethod
    def create_executor(
            cls,
            strategy: ScriptStrategyBase,
            config: ExecutorConfigFactoryProtocol,
            update_interval: float,
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
        # Register the config id (Other actions will reference this id)
        cls._executor_ids[type(config)] = cls._executor_ids.get(type(config), set()).union({config.id})
        return executor_cls(strategy, config, update_interval)

    @classmethod
    def get_update_type(cls, config_type: Type[ExecutorConfigFactoryProtocol]) -> Type[ExecutorUpdateBase] | None:
        """
        Get the update type associated with a given executor configuration type.

        :param config_type: The executor configuration type.
        :return: The update type if registered, otherwise None.
        """
        return cls._update_types.get(config_type)

    @classmethod
    def get_config_type_for_executor(cls, executor_id: str) -> Type[ExecutorConfigFactoryProtocol] | None:
        """
        Get the configuration type associated with an executor id.

        :param executor_id: The executor id.
        :return: The configuration type if found, otherwise None.
        """
        return next(
            (
                config_type
                for config_type, ids in cls._executor_ids.items()
                if executor_id in ids
            ),
            None,
        )

    @classmethod
    def get_registry(cls) -> dict[Type[ExecutorConfigFactoryProtocol], Type[ExecutorBaseFactoryProtocol]]:
        return cls._registry
