import asyncio
import time
import logging
from typing import List, Optional
from decimal import Decimal
import copy

from hummingbot.core.api_throttler.data_types import (
    CallRateLimit,
    Seconds,
    MultiLimitsTaskLog
)
from hummingbot.logger import HummingbotLogger
from hummingbot.client.config.global_config_map import global_config_map

mlpt_logger = None
MAX_CAPACITY_REACHED_WARNING_INTERVAL = 30.


class MultiLimitPoolsRequestContext:
    """
    An async context class ('async with' syntax) that checks for rate limit and wait for the capacity if needed.
    It uses async lock to prevent other instances of this class from running acquire fn before it finishes with it.
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global mlpt_logger
        if mlpt_logger is None:
            mlpt_logger = logging.getLogger(__name__)
        return mlpt_logger

    _last_max_cap_warning_ts: float = 0.

    def __init__(self,
                 task_logs: List[MultiLimitsTaskLog],
                 rate_limits: List[CallRateLimit],
                 lock: asyncio.Lock,
                 retry_interval: Seconds = 0.1):
        """
        :param task_logs: A list of task logs
        :param rate_limits: A list of rate limits appreciable to this context
        :param retry_interval: A retry interval (wait time) between each try once the rate limit is reached
        """
        self._task_logs: List[MultiLimitsTaskLog] = task_logs
        self._retry_interval: float = retry_interval
        self._rate_limits: List[CallRateLimit] = rate_limits
        self._lock = lock

    def _within_capacity(self) -> bool:
        """
        Checks if an additional task is still within all its call rate limits. Logs a warning message if the limit is
        about to reach.
        :Return: True if it is within capacity to add a new task
        """
        now: float = time.time()
        for rate_limit in self._rate_limits:
            same_pool_tasks = [t for t in self._task_logs if rate_limit in t.rate_limits and
                               now - rate_limit.period_safety_margin - t.timestamp <= rate_limit.time_interval]
            if (len(same_pool_tasks) + 1) * rate_limit.weight > rate_limit.limit:
                if self._last_max_cap_warning_ts < time.time() - MAX_CAPACITY_REACHED_WARNING_INTERVAL:
                    msg = f"API rate limit on {rate_limit.limit_id} ({rate_limit.limit} calls per " \
                          f"{rate_limit.time_interval}s) has almost reached. Number of calls " \
                          f"is {len(same_pool_tasks) * rate_limit.weight} in the last " \
                          f"{rate_limit.time_interval} seconds"
                    self.logger().notify(msg)
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
    A task can have multiple call rates (weight), though tasks are still ordered in sequence as they come (FIFO).
    For example
    Pool 0 - rate limit is 100 calls per second
    Pool 1 - rate limit is 10 calls per second
    Task A which increases rate limit for both Pool 0 and Pool 1 can be called at 10 calls per second, any calls after
    this (whether it belongs to Pool 0 or Pool 1) will have to wait for new capacity (some of the Task A flushed out).
    """

    def __init__(self,
                 rate_limits: List[CallRateLimit],
                 retry_interval: Seconds = 0.1):
        """
        :param rate_limits: A list of rate limits for the entire throttler operation
        :param retry_interval: A retry interval (wait time) between each try on the async context
        """
        # Maintains a FIFO queue of all tasks.
        self._task_logs: List[MultiLimitsTaskLog] = list()
        self._retry_interval: float = retry_interval
        limits_pct: Optional[Decimal] = global_config_map["rate_limits_share_pct"].value
        limits_pct = Decimal("1") if limits_pct is None else limits_pct / Decimal("100")
        self._rate_limits: List[CallRateLimit] = copy.deepcopy(rate_limits)
        for rate_limit in self._rate_limits:
            rate_limit.limit = int(rate_limit.limit * limits_pct)
        self._lock = asyncio.Lock()

    def execute_task(self, limit_ids: List[str]) -> MultiLimitPoolsRequestContext:
        """
        Creates an async context where code within the context (a task) can be run only when all rate
        limits have capacity for the new task.
        :param limit_ids: A list of limit_ids for rate limits supplied during init
        :return: An async context (used with async with syntax)
        """
        rate_limits: List[CallRateLimit] = [r for r in self._rate_limits if r.limit_id in limit_ids]
        return MultiLimitPoolsRequestContext(
            task_logs=self._task_logs,
            rate_limits=rate_limits,
            retry_interval=self._retry_interval,
            lock=self._lock
        )
