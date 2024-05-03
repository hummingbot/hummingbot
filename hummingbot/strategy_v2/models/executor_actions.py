from typing import Optional, Union

from pydantic import BaseModel

from hummingbot.strategy_v2.executors.arbitrage_executor.data_types import ArbitrageExecutorConfig
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.strategy_v2.executors.twap_executor.data_types import TWAPExecutorConfig
from hummingbot.strategy_v2.executors.xemm_executor.data_types import XEMMExecutorConfig


class ExecutorAction(BaseModel):
    """
    Base class for bot actions.
    """
    controller_id: Optional[str] = "main"


class CreateExecutorAction(ExecutorAction):
    """
    Action to create an executor.
    """
    executor_config: Union[PositionExecutorConfig, DCAExecutorConfig, XEMMExecutorConfig, ArbitrageExecutorConfig, TWAPExecutorConfig]


class StopExecutorAction(ExecutorAction):
    """
    Action to stop an executor.
    """
    executor_id: str


class StoreExecutorAction(ExecutorAction):
    """
    Action to store an executor.
    """
    executor_id: str
