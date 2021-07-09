import asyncio
import time

from collections import deque
from typing import Deque, List

from hummingbot.core.api_throttler.api_request_context_base import APIRequestContextBase
from hummingbot.core.api_throttler.api_throttler_base import APIThrottlerBase
from hummingbot.core.api_throttler.data_types import (
    RateLimit,
    Seconds,
    TaskLog
)


class VariedRateThrottler(APIThrottlerBase):

    def __init__(self,
                 rate_limit_list: List[RateLimit],
                 period_safety_margin: Seconds = 0.1,
                 retry_interval: Seconds = 0.5):
        super().__init__(rate_limit_list, period_safety_margin=period_safety_margin, retry_interval=retry_interval)

        # Maintains a FIFO queue of pending API requests.
        self._pending_tasks: Deque[str] = deque()

    def execute_task(self, path_url: str):
        rate_limit: RateLimit = self._path_rate_limit_map[path_url]
        task_logs: Deque[TaskLog] = self._path_task_logs_map[path_url]

        return VariedRateRequestContext(
            task_logs=task_logs,
            pending_tasks=self._pending_tasks,
            rate_limit=rate_limit,
            period_safety_margin=self._period_safety_margin,
            retry_interval=self._retry_interval,
        )


class VariedRateRequestContext(APIRequestContextBase):

    def __init__(self,
                 task_logs: Deque[TaskLog],
                 pending_tasks: Deque[str],
                 rate_limit: RateLimit,
                 period_safety_margin: Seconds = 0.1,
                 retry_interval: Seconds = 0.1):
        super().__init__(
            task_logs,
            rate_limit,
            period_safety_margin=period_safety_margin,
            retry_interval=retry_interval)

        # VariedRateThrottler has a pending_task to ensure the order in which the requests are being executed.
        self._pending_tasks = pending_tasks

    def within_capacity(self) -> bool:
        current_capacity: int = self._rate_limit.limit - len([task
                                                              for task in self._task_logs
                                                              if task.path_url == self._rate_limit.path_url])

        return current_capacity - self._rate_limit.weight >= 0

    async def acquire(self):
        self._pending_tasks.append(id(self))

        while True:
            self.flush()

            if self.within_capacity():

                if id(self) == self._pending_tasks[0]:
                    self._pending_tasks.popleft()
                    break

            await asyncio.sleep(self._retry_interval)

        task = TaskLog(timestamp=time.time(),
                       path_url=self._rate_limit.path_url,
                       weight=self._rate_limit.weight)

        self._task_logs.append(task)
        pass
