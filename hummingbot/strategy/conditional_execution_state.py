from abc import ABC, abstractmethod
from datetime import datetime

from hummingbot.strategy.strategy_base import StrategyBase


class ConditionalExecutionState(ABC):

    @abstractmethod
    def process_tick(self, strategy: StrategyBase):
        pass


class RunAlwaysExecutionState(ConditionalExecutionState):

    def process_tick(self, timestamp: float, strategy: StrategyBase):
        strategy.process_tick(timestamp)


class RunInTimeSpanExecutionState(ConditionalExecutionState):

    def __init__(self, start_timestamp: datetime, end_timestamp: datetime):
        super().__init__()

        self._start_timestamp: datetime = start_timestamp
        self._end_timestamp: datetime = end_timestamp

    def process_tick(self, timestamp: float, strategy: StrategyBase):
        if self._start_timestamp <= timestamp < self._end_timestamp:
            strategy.process_tick(timestamp)
        else:
            strategy.logger().debug("Time span execution: tick will not be processed "
                                    f"(executing between {self._start_timestamp} and {self._end_timestamp})")
