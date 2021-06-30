import logging
import time
import asyncio
from collections import deque
from enum import Enum
from typing import (
    Deque,
    Dict,
    Optional,
    Tuple,
    Union,
)


class RateLimitType(Enum):
    FIXED = 1
    WEIGHTED = 2
    PER_METHOD = 3


Limit = int         # Integer representing the no. of requests be time interval
RequestPath = str       # String representing the request path url
RequestWeight = int     # Integer representing the request weight of the path url

TimeInterval = float    # Time interval for the defined rate limits(in seconds)
Timestamp_s = float     # Current timestamp(in seconds)
Seconds = float

# TODO: Create a RateLimit class
WeightedRateLimit = Dict[RequestPath, Tuple[Limit, RequestWeight, TimeInterval]]
FixedRateLimit = Tuple[Limit, TimeInterval]
PerMethodRateLimit = Dict[RequestPath, Tuple[Limit, TimeInterval]]

RateLimit = Union[FixedRateLimit, WeightedRateLimit, PerMethodRateLimit]

FixedRateTask = Tuple[Timestamp_s]
PerMethodTask = Tuple[Timestamp_s, RequestPath]
WeightedTask = Tuple[Timestamp_s, RequestWeight]

TaskLog = Union[FixedRateTask, PerMethodTask, WeightedTask]


class APIThrottler:
    def __init__(self,
                 rate_limit: RateLimit,
                 rate_limit_type: RateLimitType = RateLimitType.FIXED,
                 period_safety_margin: Seconds = 0.1,
                 retry_interval: Seconds = 0.1):
        """
        The APIThrottler class handles the throttling of API requests through the usage of asynchronous context
        managers
        """

        self._rate_limit_type = rate_limit_type
        self._rate_limit = rate_limit
        self._retry_interval: float = retry_interval
        self._period_safety_margin = period_safety_margin

        self._task_logs: Deque[TaskLog] = deque()

    @property
    def rate_limit_type(self) -> RateLimitType:
        return self._rate_limit_type

    def weighted_task(self, path_url):
        return ThrottlerContextManager(
            task_logs=self._task_logs,
            rate_limit=self._rate_limit[path_url][0],
            rate_limit_type=self._rate_limit_type,
            time_interval=self._rate_limit[path_url][2],
            request_weight=self._rate_limit[path_url][1],
        )

    def fixed_rate_task(self):
        return ThrottlerContextManager(
            task_logs=self._task_logs,
            rate_limit=self._rate_limit[0],
            rate_limit_type=self._rate_limit_type,
            time_interval=self._rate_limit[1]
        )

    def per_method_task(self, path_url):
        return ThrottlerContextManager(
            task_logs=self._task_logs,
            rate_limit=self._rate_limit[path_url][0],
            rate_limit_type=self._rate_limit_type,
            request_path=path_url,
            time_interval=self._rate_limit[path_url][1]
        )


class ThrottlerContextManager:
    throttler_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls.throttler_logger is None:
            cls.throttler_logger = logging.getLogger(__name__)
        return cls.throttler_logger

    def __init__(self,
                 task_logs: Deque[TaskLog],
                 rate_limit: Limit,
                 rate_limit_type: RateLimitType,
                 request_weight: RequestWeight = 1,
                 request_path: RequestPath = "",
                 period_safety_margin: Seconds = 0.1,
                 time_interval: Seconds = 1.0,
                 retry_interval: Seconds = 0.1):
        """
        :param task_logs: Shared task logs
        :param rate_limit: Max API calls allowed in the given period
        :param rate_limit_type: Rate limit type
        :param request_weight: Weight of the request of the task
        :param request_path: Path URL of the API request
        :param period_safety_margin: estimate for the network latency
        :param period: Time interval of the rate limit
        :param retry_interval: Time between each limit check
        """
        self._period_safety_margin = period_safety_margin
        self._lock = asyncio.Lock()
        self._request_path = request_path
        self._request_weight: RequestWeight = request_weight
        self._rate_limit: int = rate_limit
        self._rate_limit_type: RateLimitType = rate_limit_type
        self._time_interval: float = time_interval
        self._retry_interval: float = retry_interval
        self._task_logs: Deque[TaskLog] = task_logs

    def flush(self):
        """
        Remove task logs that have passed rate limit periods
        :return:
        """
        now: float = time.time()
        while self._task_logs:
            task_log: TaskLog = self._task_logs[0]
            task_ts: float = task_log[0]
            elapsed: float = now - task_ts
            if elapsed > self._time_interval - self._period_safety_margin:
                self._task_logs.popleft()
            else:
                break

    async def acquire(self):
        while True:
            self.flush()

            if self._rate_limit_type == RateLimitType.PER_METHOD:
                current_capacity: int = self._rate_limit - len([path for _, path in self._task_logs if path == self._request_path])
            elif self._rate_limit_type == RateLimitType.FIXED:
                current_capacity: int = self._rate_limit - len(self._task_logs)
            elif self._rate_limit_type == RateLimitType.WEIGHTED:
                current_capacity: int = self._rate_limit - sum(weight for (_, weight) in self._task_logs)

            # Request Weight for non-weighted requests defaults to 1
            if current_capacity - self._request_weight > 0:
                break
            await asyncio.sleep(self._retry_interval)

        if self._rate_limit_type == RateLimitType.PER_METHOD:
            task: PerMethodTask = (time.time(), self._request_path)
        elif self._rate_limit_type == RateLimitType.FIXED:
            task: FixedRateTask = (time.time())
        elif self._rate_limit_type == RateLimitType.WEIGHTED:
            task: WeightedTask = (time.time(), self._request_weight)

        self._task_logs.append(task)

    async def __aenter__(self):
        async with self._lock:
            await self.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        pass
