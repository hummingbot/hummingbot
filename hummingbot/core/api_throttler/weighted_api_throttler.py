from typing import Deque

from hummingbot.core.api_throttler.api_request_context_base import APIRequestContextBase
from hummingbot.core.api_throttler.api_throttler_base import APIThrottlerBase
from hummingbot.core.api_throttler.data_types import RateLimit, TaskLog


class WeightedAPIThrottler(APIThrottlerBase):

    def execute_task(self, path_url: str):
        rate_limit: RateLimit = self._path_rate_limit_map[path_url]
        task_logs: Deque[TaskLog] = self._path_task_logs_map[path_url]
        return WeightedRequestContext(
            task_logs=task_logs,
            rate_limit=rate_limit,
            retry_interval=self._retry_interval,
        )


class WeightedRequestContext(APIRequestContextBase):

    def within_capacity(self) -> bool:
        current_capacity: int = self._rate_limit.limit - sum([task.weight
                                                              for task in self._task_logs
                                                              if task.path_url == self._rate_limit.path_url])

        return current_capacity - self._rate_limit.weight >= 0
