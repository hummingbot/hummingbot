from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from typing import Dict, List, Optional, Union

_T_Limit = int  # Integer representing the no. of requests be time interval
_T_RequestPath = str  # String representing the request path url
_T_RequestWeight = int  # Integer representing the request weight of the path url
_T_Seconds = Decimal
_T_Rate = Decimal
_T_Capacity = int

DEFAULT_PATH: _T_RequestPath = ""
DEFAULT_WEIGHT: _T_RequestWeight = 1


@dataclass
class LinkedLimitWeightPair:
    limit_id: _T_RequestPath
    weight: _T_RequestWeight = DEFAULT_WEIGHT


class RateLimit:
    """
    Defines call rate limits typical for API endpoints.
    """

    def __init__(self,
                 limit_id: _T_RequestPath,
                 limit: _T_Limit,
                 time_interval: Union[_T_Seconds, float],
                 weight: _T_RequestWeight = DEFAULT_WEIGHT,
                 linked_limits: Optional[List[LinkedLimitWeightPair]] = None,
                 ):
        """
        :param limit_id: A unique identifier for this RateLimit object, this is usually an API request path url
        :param limit: A total number of calls * weight permitted within time_interval period
        :param time_interval: The time interval in seconds
        :param weight: The weight (in integer) of each call. Defaults to 1
        :param linked_limits: Optional list of LinkedLimitWeightPairs. Used to associate a weight to the linked rate limit.
        """
        self.limit_id: _T_RequestPath = limit_id
        self.limit: _T_Limit = limit
        self.time_interval: _T_Seconds = time_interval if isinstance(time_interval, Decimal) else Decimal(time_interval)
        self.weight: _T_RequestWeight = weight
        self.linked_limits: List[LinkedLimitWeightPair] = linked_limits or []

    def __repr__(self):
        return f"limit_id: {self.limit_id}, limit: {self.limit}, time interval: {self.time_interval}, " \
               f"weight: {self.weight}, linked_limits: {self.linked_limits}"


class TokenBucket(RateLimit):
    """
    Defines call rate limits typical for API endpoints.
    """

    __slots__ = (
        '_capacity',
        '_rate_per_s',
        '_is_fill'
    )

    def __init__(self,
                 limit_id: _T_RequestPath,
                 rate_per_s: Union[_T_Rate, Decimal, float],
                 capacity: _T_Capacity,
                 weight: _T_RequestWeight = DEFAULT_WEIGHT,
                 is_fill: bool = True,
                 time_interval: Optional[Union[_T_Seconds, float]] = None,
                 linked_limits: Optional[List[LinkedLimitWeightPair]] = None):
        """
        :param limit_id: A unique identifier for this RateLimit object, this is usually an API request path url
        :param rate_per_s: Rate of calls per seconds
        :param capacity: Maximum calls in one second (Burst)
        :param weight: The weight (in integer) of each call. Defaults to 1
        :param linked_limits: Optional list of LinkedLimitWeightPairs. Used to associate a weight to the linked rate limit.
        """
        if rate_per_s <= 0:
            raise ValueError('rate_per_s must be > 0')

        if not isinstance(capacity, int):
            raise TypeError('capacity must be an int')

        self._rate_per_s: Fraction = Fraction(rate_per_s).limit_denominator(int(1e6))
        limit: int = self._rate_per_s.numerator

        if time_interval:
            # A time interval was provided (this is very unlikely - but needed for some tests)
            # Resetting the limit based on the provided time_interval
            limit: int = int(limit / time_interval)
        else:
            time_interval: _T_Seconds = _T_Seconds(self._rate_per_s.denominator)

        super().__init__(limit_id, limit, time_interval, weight, linked_limits)
        self._capacity: _T_Capacity = capacity
        self._is_fill: bool = is_fill

    def __repr__(self):
        return f"limit_id: {self.limit_id}, rate: {self.rate_per_s}Hz, capacity: {self.capacity}, " \
               f"weight: {self.weight}, linked_limits: {self.linked_limits}"

    @property
    def rate_per_s(self) -> Decimal:
        return self._rate_per_s.numerator / Decimal(self._rate_per_s.denominator)

    @property
    def capacity(self) -> _T_Capacity:
        return self._capacity

    @capacity.setter
    def capacity(self, value: _T_Capacity):
        self._capacity: _T_Capacity = value

    def is_fill(self) -> bool:
        return self._is_fill


_T_RateToken = Union[RateLimit, TokenBucket]
_T_Bucket = Dict[_T_RequestPath, Union[_T_Capacity, Decimal]]
_T_Buckets = Dict[_T_RequestPath, _T_Bucket]


@dataclass
class TaskLog:
    timestamp: _T_Seconds
    rate_limit: _T_RateToken
    weight: _T_RequestWeight


class LimiterMethod(Enum):
    SLIDING_WINDOW = 1
    FILL_TOKEN_BUCKET = 2
    LEAK_TOKEN_BUCKET = 3
