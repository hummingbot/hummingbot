from typing import Type

from pydantic import BaseModel, Field, root_validator, validator

from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.executor_base import ExecutorUpdateBase
from hummingbot.strategy_v2.executors.executor_factory import ExecutorFactory


class ExecutorActionType:
    """Defines available executor action types."""
    CREATE = "create"
    STOP = "stop"
    UPDATE = "update"
    STORE = "store"


class ExecutorAction(BaseModel):
    """Base class for executor actions.

    This class defines a generic action interface that is independent of
    specific executor implementations.
    """
    action_type: str = Field(..., description="Type of action")
    controller_id: str
    executor_id: str | None = None
    keep_position: bool | None = False
    executor_config: ExecutorConfigBase | None = None
    update_data: ExecutorUpdateBase | None = None

    class Config:
        frozen = True
        validate_assignment = True
        arbitrary_types_allowed = True

    @root_validator(pre=False)
    def validate_action_requirements(cls, values):
        """Validate required fields based on action type."""
        action_type = values.get("action_type")

        if action_type == ExecutorActionType.CREATE:
            if "executor_config" not in values or not values["executor_config"]:
                raise ValueError("executor_config is required for create action")

            config = values["executor_config"]

            # Then validate it's the right type
            if not isinstance(config, ExecutorConfigBase):
                raise ValueError(f"executor_config must be instance of ExecutorConfigBase, got {type(config)}")

            # Finally validate it's registered
            if not hasattr(config, "__class__") or config.__class__ not in ExecutorFactory.get_registry():
                raise ValueError(f"Executor config not registered with ExecutorFactory: {config}")

        elif action_type in (ExecutorActionType.STOP, ExecutorActionType.STORE):
            if not values.get("executor_id"):
                raise ValueError(f"executor_id is required for {action_type} action")

        elif action_type == ExecutorActionType.UPDATE:
            if not values.get("executor_id"):
                raise ValueError("executor_id is required for update action")
            if not values.get("update_data"):
                raise ValueError("update_data is required for update action")

            executor_id = values["executor_id"]
            v = values["update_data"]

            # Validate update type matches registered type
            config_type: Type[ExecutorConfigBase] | None = ExecutorFactory.get_config_type_for_executor(values["executor_id"])
            if config_type is None:
                raise ValueError(f"No executor found for id: {values['executor_id']}")

            expected_type = ExecutorFactory.get_update_type(config_type)
            if not expected_type:
                raise ValueError(f"No update type registered for config type: {config_type}")

            # Validate update data type
            if not isinstance(v, expected_type):
                raise ValueError(
                    f"Invalid update type for executor {executor_id}. "
                    f"Expected {expected_type.__name__}, got {type(v).__name__}"
                )
        return values

    @validator("action_type")
    def validate_action_type(cls, v):
        valid_action_types = {
            value for key, value in ExecutorActionType.__dict__.items()
            if not key.startswith("__") and isinstance(value, str)
        }
        if v not in valid_action_types:
            raise ValueError(f"Invalid action type: {v} not in {valid_action_types}")
        return v

    # Factory methods to provide a flexible framework
    @classmethod
    def create(
            cls,
            controller_id: str,
            executor_config: ExecutorConfigBase,
    ) -> "ExecutorAction":
        """Create a new executor.

        :param controller_id: Controller requesting the action.
        :param executor_config: Configuration for the new executor.
        :return: Action instance.
        """
        return cls(
            action_type=ExecutorActionType.CREATE,
            controller_id=controller_id,
            executor_config=executor_config,
        )

    @classmethod
    def stop(
            cls,
            controller_id: str,
            executor_id: str,
    ) -> "ExecutorAction":
        """Stop an existing executor.

        :param controller_id: Controller requesting the action.
        :param executor_id: Executor to stop.
        :return: Action instance.
        """
        return cls(
            action_type=ExecutorActionType.STOP,
            controller_id=controller_id,
            executor_id=executor_id,
        )

    @classmethod
    def store(
            cls,
            controller_id: str,
            executor_id: str,
    ) -> "ExecutorAction":
        """Store an existing executor.

        :param controller_id: Controller requesting the action.
        :param executor_id: Executor to store.
        :return: Action instance.
        """
        return cls(
            action_type=ExecutorActionType.STORE,
            controller_id=controller_id,
            executor_id=executor_id,
        )

    @classmethod
    def update(
            cls,
            controller_id: str,
            executor_id: str,
            update_data: ExecutorUpdateBase,
    ) -> "ExecutorAction":
        """Update an existing executor.

        :param controller_id: Controller requesting the action.
        :param executor_id: Executor to update.
        :param update_data: Update parameters.
        :return: Action instance.
        """
        return cls(
            action_type=ExecutorActionType.UPDATE,
            controller_id=controller_id,
            executor_id=executor_id,
            update_data=update_data,
        )


class CreateExecutorAction(ExecutorAction):
    """Create executor action."""
    action_type: str = Field(default=ExecutorActionType.CREATE, const=True)
    executor_config: ExecutorConfigBase = Field(
        ...,
        description="Configuration for the new executor",
    )


class StopExecutorAction(ExecutorAction):
    """Stop executor action."""
    action_type: str = Field(default=ExecutorActionType.STOP, const=True)
    executor_id: str = Field(
        ...,
        description="ID of executor to stop",
    )


class StoreExecutorAction(ExecutorAction):
    """Store executor action."""
    action_type: str = Field(default=ExecutorActionType.STORE, const=True)
    executor_id: str = Field(
        ...,
        description="ID of executor to stop",
    )


class UpdateExecutorAction(ExecutorAction):
    """Store executor action."""
    action_type: str = Field(default=ExecutorActionType.UPDATE, const=True)
    executor_id: str = Field(
        ...,
        description="ID of executor to stop",
    )
    update_data: ExecutorUpdateBase = Field(
        ...,
        description="Update parameters",
    )
