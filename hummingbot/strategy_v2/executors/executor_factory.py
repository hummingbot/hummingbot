import logging
from typing import Callable, Type

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.protocols import (
    ExecutorBaseFactoryProtocol,
    ExecutorBaseInfoProtocol,
    ExecutorConfigFactoryProtocol,
    ExecutorCustomInfoFactoryProtocol,
    ExecutorUpdateFactoryProtocol,
)


class ExecutorFactory:
    """
    Factory class for creating executor instances from configuration objects.

    This factory uses a registration mechanism to map ExecutorConfigFactoryProtocol types
    to concrete ExecutorBaseFactoryProtocol classes.
    """
    _registry: dict[Type[ExecutorConfigFactoryProtocol], Type[ExecutorBaseFactoryProtocol]] = {}
    _update_types: dict[Type[ExecutorConfigFactoryProtocol], Type[ExecutorUpdateFactoryProtocol]] = {}
    _custom_info_types: dict[Type[ExecutorConfigFactoryProtocol], Type[ExecutorCustomInfoFactoryProtocol]] = {}
    _executor_ids: dict[Type[ExecutorConfigFactoryProtocol], set[str]] = {}

    _logger = None

    @classmethod
    def logger(cls):
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    def register_executor(
            cls,
            config_type: Type[ExecutorConfigFactoryProtocol],
            *,
            update_type: Type[ExecutorUpdateFactoryProtocol] | None = None,
            custom_info_type: Type[ExecutorCustomInfoFactoryProtocol] | None = None,
    ) -> Callable[[Type[ExecutorBaseFactoryProtocol]], Type[ExecutorBaseFactoryProtocol]]:
        """
        Decorator to register an executor class for a given executor configuration type.

        :param config_type: The type of ExecutorConfigFactoryProtocol.
        :param update_type: The type of ExecutorUpdateFactoryProtocol.
        :param custom_info_type: The type of ExecutorCustomInfoFactoryProtocol.
        :return: A decorator that registers the executor class.
        :raises ValueError: If the executor class is already registered for the configuration type.
        :raises ValueError: If the executor class does not inherit from ExecutorBaseFactoryProtocol.
        """
        if config_type in cls._registry:
            raise ValueError(f"Executor class already registered for config type: {config_type}")

        def decorator(executor_cls: Type[ExecutorBaseFactoryProtocol]) -> Type[ExecutorBaseFactoryProtocol]:
            cls._registry[config_type] = executor_cls
            cls._update_types[config_type] = update_type
            cls._custom_info_types[config_type] = custom_info_type
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
        if not isinstance(config, ExecutorConfigFactoryProtocol):
            raise ValueError(f"Config must implement ExecutorConfigFactoryProtocol, got {type(config)}")

        if not isinstance(strategy, ScriptStrategyBase):
            raise ValueError(f"Strategy must be instance of ScriptStrategyBase, got {type(strategy)}")

        if not isinstance(update_interval, (int, float)) or update_interval <= 0:
            raise ValueError(f"Update interval must be a positive number, got {update_interval}")

        executor_cls = cls._registry.get(type(config))
        if executor_cls is None:
            raise ValueError(f"No executor registered for config type: {type(config)}")

        try:
            executor = executor_cls(strategy, config, update_interval)
            cls._executor_ids.setdefault(type(config), set()).add(config.id)
            return executor
        except Exception as e:
            raise ValueError(f"Error creating executor: {str(e)}") from e

    @classmethod
    def get_custom_info(
            cls,
            executor: ExecutorBaseInfoProtocol,
    ) -> ExecutorCustomInfoFactoryProtocol:
        """
        Create executor info instance.

        :param executor: The executor.
        :return: An instance of ExecutorInfo.
        :raises ValueError: If the executor type is not registered.
        """
        from hummingbot.strategy_v2.models.executors_info import ExecutorCustomInfoBase

        if not hasattr(executor, 'config'):
            raise ValueError(f"Executor must have a config attribute, got {executor}")

        # Return base custom info if config type not registered
        if type(executor.config) not in cls._registry:
            cls.logger().debug(f"Using default custom info for unregistered config type: {type(executor.config)}")
            return ExecutorCustomInfoBase(executor)

        # Return registered custom info type if available, otherwise default
        info_cls = cls._custom_info_types.get(type(executor.config), ExecutorCustomInfoBase)
        try:
            return info_cls(executor)
        except Exception as e:
            cls.logger().error(f"Error creating custom info for {type(executor.config)}: {str(e)}")
            return ExecutorCustomInfoBase(executor)

    @classmethod
    def get_update_type(
            cls,
            config_type: Type[ExecutorConfigFactoryProtocol]
    ) -> Type[ExecutorUpdateFactoryProtocol] | None:
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
