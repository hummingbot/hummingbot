from abc import ABC, abstractmethod
from datetime import datetime

from hummingbot.strategy.strategy_base import StrategyBase


class ConditionalExecutionState(ABC):
    """
    This class hierarchy models different execution conditions that can be used to alter the normal
    response from strategies to the tick (or c_tick) message.
    The default subclass is RunAlwaysExecutionState
    """
    @abstractmethod
    def process_tick(self, strategy: StrategyBase):
        pass


class RunAlwaysExecutionState(ConditionalExecutionState):
    """
    Execution configuration to always run the strategy for every tick
    """

    def __str__(self):
        return "run continuously"

    def process_tick(self, timestamp: float, strategy: StrategyBase):
        strategy.process_tick(timestamp)


class RunInTimeSpanExecutionState(ConditionalExecutionState):
    """
    Execution configuration to always run the strategy only for the ticks that happen between the specified start
    timestamp and stop timestamp
    :param start_timestamp: Specifies the moment to start running the strategy (datetime)
    :param end_timestamp: Specifies the moment to stop running the strategy (datetime)
    """

    def __init__(self, start_timestamp: datetime, end_timestamp: datetime):
        super().__init__()

        self._start_timestamp: datetime = start_timestamp
        self._end_timestamp: datetime = end_timestamp

    def __str__(self):
        return f"run between {self._start_timestamp} and {self._end_timestamp}"

    def process_tick(self, timestamp: float, strategy: StrategyBase):
        if self._start_timestamp.timestamp() <= timestamp < self._end_timestamp.timestamp():
            strategy.process_tick(timestamp)
        else:
            strategy.logger().debug("Time span execution: tick will not be processed "
                                    f"(executing between {self._start_timestamp.isoformat(sep=' ')} "
                                    f"and {self._end_timestamp.isoformat(sep=' ')})")
