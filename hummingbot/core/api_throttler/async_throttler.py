import time

from hummingbot.core.api_throttler.async_request_context_base import (
    AsyncRequestContextBase,
    MAX_CAPACITY_REACHED_WARNING_INTERVAL,
)
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase


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
        if len(self._related_limits) > 0:
            now: float = time.time()
            for rate_limit, weight in self._related_limits:
                capacity_used: int = sum([task.weight
                                          for task in self._task_logs
                                          if rate_limit.limit_id == task.rate_limit.limit_id and
                                          now - task.timestamp - (task.rate_limit.time_interval * self._safety_margin_pct) <= task.rate_limit.time_interval])

                if capacity_used + weight > rate_limit.limit:
                    if self._last_max_cap_warning_ts < now - MAX_CAPACITY_REACHED_WARNING_INTERVAL:
                        msg = f"API rate limit on {rate_limit.limit_id} ({rate_limit.limit} calls per " \
                              f"{rate_limit.time_interval}s) has almost reached. Limits used " \
                              f"is {capacity_used} in the last " \
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

    def execute_task(self, limit_id: str) -> AsyncRequestContext:
        """
        Creates an async context where code within the context (a task) can be run only when all rate
        limits have capacity for the new task.
        :param limit_id: the limit_id associated with the APi request
        :return: An async context (used with async with syntax)
        """
        rate_limit, related_rate_limits = self.get_related_limits(limit_id=limit_id)
        return AsyncRequestContext(
            task_logs=self._task_logs,
            rate_limit=rate_limit,
            related_limits=related_rate_limits,
            lock=self._lock,
            safety_margin_pct=self._safety_margin_pct,
            retry_interval=self._retry_interval,
        )
