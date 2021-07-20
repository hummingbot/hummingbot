import asyncio
import time
import logging
from typing import List

from hummingbot.core.api_throttler.data_types import (
    CallRateLimit,
    Seconds,
    MultiLimitsTaskLog
)
from hummingbot.logger import HummingbotLogger

mlpt_logger = None
MAX_CAPACITY_REACHED_WARNING_INTERVAL = 10.


class MultiLimitPoolsRequestContext:
    """
    An async context class (use it with async with syntax) with a lock to prevent other instance from running acquire
    before it finishes with it.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global mlpt_logger
        if mlpt_logger is None:
            mlpt_logger = logging.getLogger(__name__)
        return mlpt_logger

    _lock = asyncio.Lock()
    _last_max_cap_warning_ts: float = 0.

    def __init__(self,
                 task_logs: List[MultiLimitsTaskLog],
                 rate_limits: List[CallRateLimit],
                 retry_interval: Seconds = 0.1):
        """
        :param task_logs: A list of current active tasks
        :param rate_limits: A list of rate limits appreciable to this context
        :param retry_interval: A retry interval (wait time) between each try once the rate limit is reached
        """
        self._task_logs: List[MultiLimitsTaskLog] = task_logs
        self._rate_limits: List[CallRateLimit] = rate_limits
        self._retry_interval: float = retry_interval

    def _within_capacity(self) -> bool:
        """
        Check if an additional task is still within all its call rate limits.
        :Return: True if it is within capacity to add a new task
        """
        now: float = time.time()
        for rate_limit in self._rate_limits:
            same_pool_tasks = [t for t in self._task_logs if rate_limit in t.rate_limits and
                               now - rate_limit.period_safety_margin - t.timestamp <= rate_limit.time_interval]
            if (len(same_pool_tasks) + 1) * rate_limit.weight > rate_limit.limit:
                if self._last_max_cap_warning_ts < time.time() - MAX_CAPACITY_REACHED_WARNING_INTERVAL:
                    self.logger().warning(f"A rate limit on {rate_limit.limit_id} has almost reached. Number of calls "
                                          f"is {len(same_pool_tasks) * rate_limit.weight} in the last "
                                          f"{rate_limit.time_interval} seconds")
                    MultiLimitPoolsRequestContext._last_max_cap_warning_ts = time.time()
                return False
        return True

    def _flush(self):
        """
        Remove task logs that have passed rate limit periods
        """
        now: float = time.time()
        for task in self._task_logs:
            elapsed: float = now - task.timestamp
            if all(elapsed > limit.time_interval + limit.period_safety_margin for limit in task.rate_limits):
                self._task_logs.remove(task)

    async def _acquire(self):
        """
        Keeps trying on adding a new task, if limit is reaches it waits for retry_interval before trying again.
        """
        while True:
            self._flush()
            if self._within_capacity():
                break
            await asyncio.sleep(self._retry_interval)
        task = MultiLimitsTaskLog(timestamp=time.time(), rate_limits=self._rate_limits)
        self._task_logs.append(task)

    async def __aenter__(self):
        async with self._lock:
            await self._acquire()

    async def __aexit__(self, exc_type, exc, tb):
        pass


class MultiLimitPoolsThrottler:
    """
    Handles call rate limits by providing async context (async with), it delays as needed to make sure calls stay
    within defined limits.
    A task can have multiple call rates (weight), though tasks are still ordered in sequence and they come (FIFO).
    For example
    Pool 0 - rate limit is 100 calls per second
    Pool 1 - rate limit is 10 calls per second
    Task A which increases rate limit for both Pool 0 and Pool 1 can be called at 10 calls per second, any calls after
    this (whether it belongs to Pool 0 or Pool 1) will have to wait for capacity (some of the Task A flushed out).
    """

    def __init__(self,
                 rate_limit_list: List[CallRateLimit],
                 retry_interval: Seconds = 0.1):
        """
        :param rate_limit_list: A list of rate limits for the entire throttler operation
        :param retry_interval: A retry interval (wait time) between each try on the async context
        """
        self._rate_limit_list: List[CallRateLimit] = rate_limit_list
        self._retry_interval: float = retry_interval
        # Maintains a FIFO queue of all tasks.
        self._task_logs: List[MultiLimitsTaskLog] = list()

    def execute_task(self, limit_ids: List[str]) -> MultiLimitPoolsRequestContext:
        rate_limits: List[CallRateLimit] = [r for r in self._rate_limit_list if r.limit_id in limit_ids]
        return MultiLimitPoolsRequestContext(
            task_logs=self._task_logs,
            rate_limits=rate_limits,
            retry_interval=self._retry_interval,
        )
