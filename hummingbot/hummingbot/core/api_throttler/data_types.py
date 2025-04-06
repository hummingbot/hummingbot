from dataclasses import dataclass
from typing import (
    List,
    Optional,
)

DEFAULT_PATH = ""
DEFAULT_WEIGHT = 1

Limit = int             # Integer representing the no. of requests be time interval
RequestPath = str       # String representing the request path url
RequestWeight = int     # Integer representing the request weight of the path url
Seconds = float


@dataclass
class LinkedLimitWeightPair:
    limit_id: str
    weight: int = DEFAULT_WEIGHT


class RateLimit:
    """
    Defines call rate limits typical for API endpoints.
    """

    def __init__(self,
                 limit_id: str,
                 limit: int,
                 time_interval: float,
                 weight: int = DEFAULT_WEIGHT,
                 linked_limits: Optional[List[LinkedLimitWeightPair]] = None,
                 ):
        """
        :param limit_id: A unique identifier for this RateLimit object, this is usually an API request path url
        :param limit: A total number of calls * weight permitted within time_interval period
        :param time_interval: The time interval in seconds
        :param weight: The weight (in integer) of each call. Defaults to 1
        :param linked_limits: Optional list of LinkedLimitWeightPairs. Used to associate a weight to the linked rate limit.
        """
        self.limit_id = limit_id
        self.limit = limit
        self.time_interval = time_interval
        self.weight = weight
        self.linked_limits = linked_limits or []

    def __repr__(self):
        return f"limit_id: {self.limit_id}, limit: {self.limit}, time interval: {self.time_interval}, " \
               f"weight: {self.weight}, linked_limits: {self.linked_limits}"


@dataclass
class TaskLog:
    timestamp: float
    rate_limit: RateLimit
    weight: int
