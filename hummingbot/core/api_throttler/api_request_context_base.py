import asyncio
import time

from abc import ABC, abstractmethod
from typing import (
    Deque,
)

from hummingbot.core.api_throttler.data_types import (
    RateLimit,
    TaskLog,
    Seconds
)


class APIRequestContextBase(ABC):

    _lock = asyncio.Lock()

    def __init__(self,
                 task_logs: Deque[TaskLog],
                 rate_limit: RateLimit,
                 period_safety_margin: Seconds = 0.1,
                 retry_interval: Seconds = 0.1):
        """
        Asynchronous context associated with each API request.
        :param task_logs: Shared task logs
        :param rate_limit: Rate limit for the associated API request
        :param period_safety_margin: estimate for the network latency
        :param retry_interval: Time between each limit check
        """
        self._task_logs: Deque[TaskLog] = task_logs

        self._rate_limit: RateLimit = rate_limit

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

    @abstractmethod
    def within_capacity(self) -> bool:
        raise NotImplementedError

    async def acquire(self):
        while True:
            self.flush()

            if self.within_capacity():
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
