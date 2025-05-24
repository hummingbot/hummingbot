import time
from decimal import Decimal
from typing import Dict, List, Tuple

from hummingbot.core.api_throttler.async_request_context_base import (
    MAX_CAPACITY_REACHED_WARNING_INTERVAL,
    AsyncRequestContextBase,
)
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.api_throttler.data_types import RateLimit, RateLimitType, TaskLog


class AsyncRequestContext(AsyncRequestContextBase):
    """
    An async context class ('async with' syntax) that checks for rate limit and wait for the capacity if needed.
    It uses async lock to prevent other instances of this class from running acquire fn before it finishes with it.
    """

    def __init__(self,
                 task_logs: List[TaskLog],
                 rate_limit: RateLimit,
                 related_limits: List[Tuple[RateLimit, int]],
                 lock,
                 safety_margin_pct: float,
                 retry_interval: float = 0.1,
                 decay_usage: Dict[str, Tuple[float, float]] = {}
                 ):
        super().__init__(task_logs, rate_limit, related_limits, lock, safety_margin_pct, retry_interval, decay_usage)

    def within_capacity(self) -> bool:
        """
        Checks if an additional task is within the defined RateLimit(s).
        For fixed window limits, it counts tasks within the time window.
        For decay-based limits, it calculates effective usage with time-based decay.

        :return: True if it is within capacity to add a new task
        """
        if self._rate_limit is None:
            return True

        list_of_limits: List[Tuple[RateLimit, int]] = [(self._rate_limit, self._rate_limit.weight)] + self._related_limits
        now: float = self._time()

        for rate_limit, weight in list_of_limits:
            if rate_limit.limit_type == RateLimitType.DECAY:
                # For decay-based limits, calculate current usage with decay applied
                current_usage = self._calculate_decay_usage(rate_limit, now)

                # Check if adding this weight would exceed the limit
                if current_usage + weight > rate_limit.limit:
                    if self._last_max_cap_warning_ts < now - MAX_CAPACITY_REACHED_WARNING_INTERVAL:
                        msg = f"API rate limit on {rate_limit.limit_id} (decay-based, current usage: {current_usage:.2f}/{rate_limit.limit}) " \
                            f"would be exceeded by request with weight {weight}. " \
                            f"Decay rate: {rate_limit.decay_rate} units/second."
                        self.logger().notify(msg)
                        AsyncRequestContextBase._last_max_cap_warning_ts = now
                    return False
            else:
                capacity_used: int = sum([
                    task.weight
                    for task in self._task_logs
                    if rate_limit.limit_id == task.rate_limit.limit_id and
                    Decimal(str(now)) - Decimal(str(task.timestamp)) - Decimal(str(rate_limit.time_interval * self._safety_margin_pct)) <= task.rate_limit.time_interval
                ])

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

    def _time(self):
        return time.time()

    def _calculate_decay_usage(self, rate_limit: RateLimit, now: float) -> float:
        """
        Calculate current usage for a decay-based rate limit by applying decay to the total usage
        """
        limit_id = rate_limit.limit_id
        last_usage, last_timestamp = self._decay_usage.get(limit_id, (0.0, now))

        # Calculate time elapsed since last update
        elapsed = now - last_timestamp

        # Apply decay to the total usage
        current_usage = max(0.0, last_usage - (rate_limit.decay_rate * elapsed))

        # Find any new tasks since the last calculation
        new_tasks = [
            task for task in self._task_logs
            if task.rate_limit.limit_id == limit_id and task.timestamp > last_timestamp
        ]

        # Add weights from new tasks
        for task in new_tasks:
            current_usage += task.weight

        # Update the cache with current values
        self._decay_usage[limit_id] = (current_usage, now)

        return current_usage

    async def acquire(self):
        """
        Override the base acquire method to update the decay_usage after acquisition
        """
        await super().acquire()

        if self._rate_limit and self._rate_limit.limit_type == RateLimitType.DECAY:
            limit_id = self._rate_limit.limit_id
            now = self._time()
            current_usage, _ = self._decay_usage.get(limit_id, (0.0, now))
            current_usage += self._rate_limit.weight
            self._decay_usage[limit_id] = (current_usage, now)

            # Also update for related limits
            for related_limit, weight in self._related_limits:
                if related_limit.limit_type == RateLimitType.DECAY:
                    related_id = related_limit.limit_id
                    related_usage, _ = self._decay_usage.get(related_id, (0.0, now))
                    related_usage += weight
                    self._decay_usage[related_id] = (related_usage, now)


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
            decay_usage=self._decay_usage
        )
