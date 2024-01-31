from typing import Dict

import pandas as pd
from pydantic import BaseModel, validator

from hummingbot.smart_components.executors.dca_executor.data_types import DCAConfig
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.models.base import SmartComponentStatus


class ExecutorHandlerReport(BaseModel):
    status: SmartComponentStatus
    active_position_executors: pd.DataFrame
    active_position_executors_info: Dict
    closed_position_executors_info: Dict
    dca_executors: pd.DataFrame

    @validator('active_position_executors', 'dca_executors', allow_reuse=True)
    def validate_dataframe(cls, v):
        if not isinstance(v, pd.DataFrame):
            raise ValueError('active_executors must be a pandas DataFrame')
        return v

    class Config:
        arbitrary_types_allowed = True


class BotAction(BaseModel):
    """
    Base class for bot actions.
    """
    pass


class CreatePositionExecutorAction(BotAction):
    """
    Action to create an executor.
    """
    level_id: str
    position_config: PositionExecutorConfig


class StopExecutorAction(BotAction):
    """
    Action to stop an executor.
    """
    executor_id: str


class StoreExecutorAction(BotAction):
    """
    Action to store an executor.
    """
    executor_id: str


class CreateDCAExecutorAction(BotAction):
    """
    Action to create a DCA executor.
    """
    dca_config: DCAConfig
    dca_id: str


class StopDCAExecutorAction(BotAction):
    """
    Action to stop a DCA executor.
    """
    dca_id: str


class StoreDCAExecutorAction(BotAction):
    """
    Action to store a DCA executor.
    """
    dca_id: str
