from dataclasses import dataclass
from typing import List

DEFAULT_PATH = ""
DEFAULT_WEIGHT = 1


class RateLimit:
    """
    Defines call rate limits typical for API endpoints.
    """

    def __init__(self,
                 limit_id: str,
                 limit: int,
                 time_interval: float,
                 weight: int = 1,
                 ):
        """
        :param limit_id: A unique identifier for this RateLimit object, this is usually an API request path
        :param limit: A total number of calls * weight permitted within time_interval period
        :param time_interval: The time interval
        :param weight: The weight (in integer) of each call
        :param period_safety_margin: An extra safety margin, in seconds, to make sure calls are within the limit,
        if not supplied this is 5% of the limit
        """
        self.limit_id = limit_id
        self.limit = limit
        self.time_interval = time_interval
        self.weight = weight

    def __repr__(self):
        return f"limit_id: {self.limit_id}, limit: {self.limit}, time interval: {self.time_interval}, " \
               f"weight: {self.weight}"


@dataclass
class TaskLog:
    timestamp: float
    rate_limits: List[RateLimit]
