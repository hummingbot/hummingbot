from hummingbot.core.api_throttler.api_request_context_base import APIRequestContextBase
from hummingbot.core.api_throttler.api_throttler_base import APIThrottlerBase
from hummingbot.core.api_throttler.data_types import RateLimit


class FixedRateThrottler(APIThrottlerBase):

    def execute_task(self):
        rate_limit: RateLimit = next(iter(self._path_rate_limit_map.values()))

        return FixedRateRequestContext(
            task_logs=self._task_logs,
            rate_limit=rate_limit,
            retry_interval=self._retry_interval,
        )


class FixedRateRequestContext(APIRequestContextBase):

    def within_capacity(self) -> bool:
        current_capacity: int = self._rate_limit.limit - len(self._task_logs)

        return current_capacity - self._rate_limit.weight >= 0
