import asyncio
import time

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import (
    Deque,
    Dict,
    List,
)


class RateLimitType(Enum):
    FIXED = 1
    WEIGHTED = 2
    PER_METHOD = 3


@dataclass
class RateLimit():
    limit: int
    time_interval: float
    path_url: str = ""
    weight: int = 1


@dataclass
class TaskLog():
    timestamp: float
    path_url: str = ""
    weight: int = 1


Limit = int             # Integer representing the no. of requests be time interval
RequestPath = str       # String representing the request path url
RequestWeight = int     # Integer representing the request weight of the path url

Seconds = float


class APIThrottler:
    def __init__(self,
                 rate_limit_list: List[RateLimit],
                 rate_limit_type: RateLimitType = RateLimitType.FIXED,
                 period_safety_margin: Seconds = 0.1,
                 retry_interval: Seconds = 0.1):
        """
        The APIThrottler class handles the throttling of API requests through the usage of asynchronous context
        managers
        """

        # Rate Limit Definitions
        self._rate_limit_type: RateLimitType = rate_limit_type
        self._rate_limit_list: List[RateLimit] = rate_limit_list

        self._path_rate_limit_map: Dict[RequestPath, RateLimit] = {
            limit.path_url: limit
            for limit in self._rate_limit_list
        }

        # Throttler Parameters
        self._retry_interval: float = retry_interval
        self._period_safety_margin = period_safety_margin

        self._task_logs: Deque[TaskLog] = deque()

    def weighted_task(self, path_url: str):
        rate_limit: RateLimit = self._path_rate_limit_map[path_url]

        return APIRequestContext(
            task_logs=self._task_logs,
            rate_limit=rate_limit,
            rate_limit_type=self._rate_limit_type,
            retry_interval=self._retry_interval,
        )

    def fixed_rate_task(self):
        rate_limit: RateLimit = next(iter(self._path_rate_limit_map.values()))

        return APIRequestContext(
            task_logs=self._task_logs,
            rate_limit=rate_limit,
            rate_limit_type=self._rate_limit_type,
            retry_interval=self._retry_interval,
        )

    def per_method_task(self, path_url):
        rate_limit: RateLimit = self._path_rate_limit_map[path_url]

        return APIRequestContext(
            task_logs=self._task_logs,
            rate_limit=rate_limit,
            rate_limit_type=self._rate_limit_type,
            retry_interval=self._retry_interval,
        )


class APIRequestContext:

    def __init__(self,
                 task_logs: Deque[TaskLog],
                 rate_limit: RateLimit,
                 rate_limit_type: RateLimitType,
                 period_safety_margin: Seconds = 0.1,
                 retry_interval: Seconds = 0.1):
        """
        Asynchronous context associated with each API request.
        :param task_logs: Shared task logs
        :param rate_limit: Rate limit for the associated API request
        :param rate_limit_type: Rate limit type
        :param period_safety_margin: estimate for the network latency
        :param retry_interval: Time between each limit check
        """
        self._lock = asyncio.Lock()
        self._task_logs: Deque[TaskLog] = task_logs

        self._rate_limit: RateLimit = rate_limit
        self._rate_limit_type: RateLimitType = rate_limit_type

        self._time_interval: float = rate_limit.time_interval
        self._retry_interval: float = retry_interval
        self._period_safety_margin = period_safety_margin

    def flush(self):
        """
        Remove task logs that have passed rate limit periods
        :return:
        """
        now: float = time.time()
        while self._task_logs:
            task_log: TaskLog = self._task_logs[0]
            elapsed: float = now - task_log.timestamp
            if elapsed > self._time_interval - self._period_safety_margin:
                self._task_logs.popleft()
            else:
                break

    async def acquire(self):
        while True:
            self.flush()

            if self._rate_limit_type == RateLimitType.PER_METHOD:
                current_capacity: int = self._rate_limit.limit - len([task
                                                                      for task in self._task_logs
                                                                      if task.path_url == self._rate_limit.path_url])
            elif self._rate_limit_type == RateLimitType.FIXED:
                current_capacity: int = self._rate_limit.limit - len(self._task_logs)
            elif self._rate_limit_type == RateLimitType.WEIGHTED:
                current_capacity: int = self._rate_limit.limit - sum([task.weight
                                                                      for task in self._task_logs
                                                                      if task.path_url == self._rate_limit.path_url])

            # Request Weight for non-weighted requests defaults to 1
            if current_capacity - self._rate_limit.weight >= 0:
                break
            await asyncio.sleep(self._retry_interval)

        task = TaskLog(timestamp=time.time(),
                       path_url=self._rate_limit.path_url,
                       weight=self._rate_limit.weight)

        self._task_logs.append(task)

    async def __aenter__(self):
        async with self._lock:
            await self.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        pass
