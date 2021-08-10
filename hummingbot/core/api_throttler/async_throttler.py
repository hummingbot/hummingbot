import time

from typing import (
    List,
)

from hummingbot.core.api_throttler.async_request_context_base import (
    AsyncRequestContextBase,
    MAX_CAPACITY_REACHED_WARNING_INTERVAL,
)
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.api_throttler.data_types import (
    RateLimit,
)


class AsyncRequestContext(AsyncRequestContextBase):
    """
    An async context class ('async with' syntax) that checks for rate limit and wait for the capacity if needed.
    It uses async lock to prevent other instances of this class from running acquire fn before it finishes with it.
    """

    def within_capacity(self) -> bool:
        """
        Checks if an additional task within the defined RateLimit(s). Logs a warning message if the limit is about to be reached.
        Note: A task can be associated to one or more RateLimit.
        :return: True if it is within capacity to add a new task
        """
        now: float = time.time()
        for rate_limit in self._rate_limits:
            same_pool_tasks = [task
                               for task in self._task_logs
                               if rate_limit in task.rate_limits
                               ]
            if (len(same_pool_tasks) + 1) * rate_limit.weight > rate_limit.limit:
                if self._last_max_cap_warning_ts < now - MAX_CAPACITY_REACHED_WARNING_INTERVAL:
                    msg = f"API rate limit on {rate_limit.limit_id} ({rate_limit.limit} calls per " \
                          f"{rate_limit.time_interval}s) has almost reached. Number of calls " \
                          f"is {len(same_pool_tasks) * rate_limit.weight} in the last " \
                          f"{rate_limit.time_interval} seconds"
                    self.logger().notify(msg)
                    AsyncRequestContextBase._last_max_cap_warning_ts = now
                return False
        return True


class AsyncThrottler(AsyncThrottlerBase):
    """
    Handles call rate limits by providing async context (async with), it delays as needed to make sure calls stay
    within defined limits.
    A task can have multiple call rates (weight), though tasks are still ordered in sequence as they come (FIFO).
    (i.e)
        Pool 0 - rate limit is 100 calls per second
        Pool 1 - rate limit is 10 calls per second
        Task A which consumes capacity from both Pool 0 and Pool 1 can be called at 10 calls per second, any calls after
        this (whether it belongs to Pool 0 or Pool 1) will have to wait for new capacity (some of the Task A flushed out).
    """

    def execute_task(self, limit_ids: List[str]) -> AsyncRequestContext:
        """
        Creates an async context where code within the context (a task) can be run only when all rate
        limits have capacity for the new task.
        :param limit_ids: A list of limit_ids for rate limits supplied during init
        :return: An async context (used with async with syntax)
        """
        rate_limits: List[RateLimit] = [limit
                                        for limit in self._rate_limits
                                        if limit.limit_id in limit_ids]
        return AsyncRequestContext(
            task_logs=self._task_logs,
            rate_limits=rate_limits,
            lock=self._lock,
            safety_margin_pct=self._safety_margin_pct,
            retry_interval=self._retry_interval,
        )
