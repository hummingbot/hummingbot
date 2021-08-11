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
                 linked_limits: List[str] = [],
                 ):
        """
        :param limit_id: A unique identifier for this RateLimit object, this is usually an API request path url
        :param limit: A total number of calls * weight permitted within time_interval period
        :param time_interval: The time interval
        :param weight: The weight (in integer) of each call. Defaults to 1
        :param pools: The API pools associated with this API request. Defaults to an empty list
        """
        self.limit_id = limit_id
        self.limit = limit
        self.time_interval = time_interval
        self.weight = weight
        self.linked_limits = linked_limits

    def __repr__(self):
        return f"limit_id: {self.limit_id}, limit: {self.limit}, time interval: {self.time_interval}, " \
               f"weight: {self.weight}, pools: {self.pools}, is_pool: {self.is_pool}"


@dataclass
class TaskLog:
    timestamp: float
    rate_limits: List[RateLimit]
