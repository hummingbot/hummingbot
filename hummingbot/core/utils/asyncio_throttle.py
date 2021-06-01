import logging
import time
import asyncio
from collections import deque
from typing import (
    Optional,
    Tuple,
    Deque
)

RequestWeight = int
Seconds = float
Timestamp_s = float
TaskLog = Tuple[Timestamp_s, RequestWeight]


class Throttler:
    def __init__(self,
                 rate_limit: Tuple[RequestWeight, Seconds],
                 period_safety_margin: Seconds = 0.1,
                 retry_interval: Seconds = 0.1):
        """
        :param rate_limit: Max weight allowed in the given period
        :param retry_interval: Time between each limit check
        """
        self._rate_limit_weight: int = rate_limit[0]
        self._period: float = rate_limit[1]
        self._retry_interval: float = retry_interval
        self._period_safety_margin = period_safety_margin
        self._task_logs: Deque[TaskLog] = deque()

    def weighted_task(self,
                      request_weight):
        return ThrottlerContextManager(
            rate_limit=self._rate_limit_weight,
            period=self._period,
            request_weight=request_weight,
            task_logs=self._task_logs)


class ThrottlerContextManager:
    throttler_logger: Optional[logging.Logger] = None

    @classmethod
    def logger(cls) -> logging.Logger:
        if cls.throttler_logger is None:
            cls.throttler_logger = logging.getLogger(__name__)
        return cls.throttler_logger

    def __init__(self,
                 task_logs: Deque[TaskLog],
                 rate_limit: RequestWeight,
                 request_weight: RequestWeight = 1,
                 period_safety_margin: Seconds = 0.1,
                 period: Seconds = 1.0,
                 retry_interval: Seconds = 0.1):
        """
        :param task_logs: Shared task logs
        :param rate_limit: Max weight allowed in the given period
        :param request_weight: Weight of the request of the added task
        :param period_safety_margin: estimate for the network latency
        :param period: Time interval of the rate limit
        :param retry_interval: Time between each limit check
        """
        self._period_safety_margin = period_safety_margin
        self._lock = asyncio.Lock()
        self._request_weight: RequestWeight = request_weight
        self._rate_limit: int = rate_limit
        self._period: float = period
        self._retry_interval: float = retry_interval
        self._task_logs: Deque[TaskLog] = task_logs

    def flush(self):
        """
        Remove task logs that have passed rate limit periods
        :return:
        """
        now: float = time.time()
        while self._task_logs:
            task_ts, _ = self._task_logs[0]
            elapsed: float = now - task_ts
            if elapsed > self._period - self._period_safety_margin:
                self._task_logs.popleft()
            else:
                break

    async def acquire(self):
        while True:
            self.flush()
            current_capacity: int = self._rate_limit - sum(weight for (ts, weight) in self._task_logs)
            if current_capacity - self._request_weight > 0:
                break
            await asyncio.sleep(self._retry_interval)
        self._task_logs.append((time.time(), self._request_weight))

    async def __aenter__(self):
        async with self._lock:
            await self.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        pass
