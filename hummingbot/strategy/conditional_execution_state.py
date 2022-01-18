from abc import ABC, abstractmethod
from datetime import datetime
from datetime import time
from typing import (
    Union,
)

from hummingbot.strategy.strategy_base import StrategyBase


class ConditionalExecutionState(ABC):
    """
    This class hierarchy models different execution conditions that can be used to alter the normal
    response from strategies to the tick (or c_tick) message.
    The default subclass is RunAlwaysExecutionState
    """

    _closing_time: int = None
    _time_left: int = None

    @property
    def time_left(self):
        return self._time_left

    @time_left.setter
    def time_left(self, value):
        self._time_left = value

    @property
    def closing_time(self):
        return self._closing_time

    @closing_time.setter
    def closing_time(self, value):
        self._closing_time = value

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
        self._closing_time = None
        self._time_left = None
        strategy.process_tick(timestamp)


class RunInTimeConditionalExecutionState(ConditionalExecutionState):
    """
    Execution configuration to always run the strategy only for the ticks that happen between the specified start
    timestamp and stop timestamp
    :param start_timestamp: Specifies the moment to start running the strategy (datetime or datetime.time)
    :param end_timestamp: Specifies the moment to stop running the strategy (datetime or datetime.time)
    """

    def __init__(self, start_timestamp: Union[datetime, time], end_timestamp: Union[datetime, time] = None):
        super().__init__()

        self._start_timestamp: Union[datetime, time] = start_timestamp
        self._end_timestamp: Union[datetime, time] = end_timestamp

    def __str__(self):
        if type(self._start_timestamp) is datetime:
            if self._end_timestamp is not None:
                return f"run between {self._start_timestamp} and {self._end_timestamp}"
            else:
                return f"run from {self._start_timestamp}"
        if type(self._start_timestamp) is time:
            if self._end_timestamp is not None:
                return f"run daily between {self._start_timestamp} and {self._end_timestamp}"

    def process_tick(self, timestamp: float, strategy: StrategyBase):
        if isinstance(self._start_timestamp, datetime):
            # From datetime
            # From datetime to datetime
            if self._end_timestamp is not None:

                self._closing_time = (self._end_timestamp.timestamp() - self._start_timestamp.timestamp()) * 1000

                if self._start_timestamp.timestamp() <= timestamp < self._end_timestamp.timestamp():
                    self._time_left = max((self._end_timestamp.timestamp() - timestamp) * 1000, 0)
                    strategy.process_tick(timestamp)
                else:
                    self._time_left = 0
                    strategy.logger().debug("Time span execution: tick will not be processed "
                                            f"(executing between {self._start_timestamp.isoformat(sep=' ')} "
                                            f"and {self._end_timestamp.isoformat(sep=' ')})")
            else:
                self._closing_time = None
                self._time_left = None
                if self._start_timestamp.timestamp() <= timestamp:
                    strategy.process_tick(timestamp)
                else:
                    strategy.logger().debug("Delayed start execution: tick will not be processed "
                                            f"(executing from {self._start_timestamp.isoformat(sep=' ')})")
        if isinstance(self._start_timestamp, time):
            # Daily between times
            if self._end_timestamp is not None:

                self._closing_time = (datetime.combine(datetime.today(), self._end_timestamp) - datetime.combine(datetime.today(), self._start_timestamp)).total_seconds() * 1000
                current_time = datetime.fromtimestamp(timestamp).time()

                if self._start_timestamp <= current_time < self._end_timestamp:
                    self._time_left = max((datetime.combine(datetime.today(), self._end_timestamp) - datetime.combine(datetime.today(), current_time)).total_seconds() * 1000, 0)
                    strategy.process_tick(timestamp)
                else:
                    self._time_left = 0
                    strategy.logger().debug("Time span execution: tick will not be processed "
                                            f"(executing between {self._start_timestamp} "
                                            f"and {self._end_timestamp})")
