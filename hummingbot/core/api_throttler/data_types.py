from dataclasses import dataclass
from typing import List

DEFAULT_PATH = ""
DEFAULT_WEIGHT = 1


Limit = int             # Integer representing the no. of requests be time interval
RequestPath = str       # String representing the request path url
RequestWeight = int     # Integer representing the request weight of the path url
Seconds = float


@dataclass
class RateLimit:
    limit: Limit
    time_interval: Seconds
    path_url: RequestPath = DEFAULT_PATH
    weight: RequestWeight = DEFAULT_WEIGHT


@dataclass
class TaskLog:
    timestamp: float
    path_url: RequestPath = DEFAULT_PATH
    weight: RequestWeight = DEFAULT_WEIGHT


class CallRateLimit:
    """
    Defines call rate limits typical for API endpoints.
    """
    def __init__(self,
                 limit_id: str,
                 limit: Limit,
                 time_interval: Seconds,
                 weight: Limit = 1,
                 period_safety_margin: Seconds = None,
                 ):
        """
        :param limit_id: A unique identifier for this CallRateLimit object, this is usually an API request path
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
        self.period_safety_margin = time_interval * 0.05 if period_safety_margin is None else period_safety_margin

    def __repr__(self):
        return f"limit_id: {self.limit_id}, limit: {self.limit}, time interval: {self.time_interval}, " \
               f"weight: {self.weight}, period_safety_margin: {self.period_safety_margin}"


@dataclass
class MultiLimitsTaskLog:
    timestamp: float
    rate_limits: List[CallRateLimit]
