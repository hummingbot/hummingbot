import asyncio
import logging
import time

from abc import ABC, abstractmethod
from typing import (
    List,
    Tuple,
)

from hummingbot.core.api_throttler.data_types import (
    RateLimit,
    TaskLog,
)
from hummingbot.logger.logger import HummingbotLogger

arc_logger = None
MAX_CAPACITY_REACHED_WARNING_INTERVAL = 30.0


class AsyncRequestContextBase(ABC):
    """
    An async context class ('async with' syntax) that checks for rate limit and waits for the capacity to be freed.
    It uses an async lock to prevent multiple instances of this class from accessing the `acquire()` function.
    """

    _last_max_cap_warning_ts: float = 0.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global arc_logger
        if arc_logger is None:
            arc_logger = logging.getLogger(__name__)
        return arc_logger

    def __init__(self,
                 task_logs: List[TaskLog],
                 rate_limit: RateLimit,
                 related_limits: List[Tuple[RateLimit, int]],
                 lock: asyncio.Lock,
                 safety_margin_pct: float,
                 retry_interval: float = 0.1,
                 ):
        """
        Asynchronous context associated with each API request.
        :param task_logs: Shared task logs associated with this API request
        :param rate_limit: The RateLimit associated with this API Request
        :param rate_limits: List of linked rate limits with its corresponding weight associated with this API Request
        :param lock: A shared asyncio.Lock used between all instances of APIRequestContextBase
        :param retry_interval: Time between each limit check
        """
        self._task_logs: List[TaskLog] = task_logs
        self._rate_limit: RateLimit = rate_limit
        self._related_limits: List[Tuple[RateLimit, int]] = related_limits
        self._lock: asyncio.Lock = lock
        self._safety_margin_pct: float = safety_margin_pct
        self._retry_interval: float = retry_interval

    def flush(self):
        """
        Remove task logs that have passed rate limit periods
        :return:
        """
        now: float = time.time()
        for task in self._task_logs:
            task_limit: RateLimit = task.rate_limit
            elapsed: float = now - task.timestamp
            if elapsed > task_limit.time_interval + (task_limit.time_interval * self._safety_margin_pct):
                self._task_logs.remove(task)

    @abstractmethod
    def within_capacity(self) -> bool:
        raise NotImplementedError

    async def acquire(self):
        while True:
            async with self._lock:
                self.flush()

                if self.within_capacity():
                    break
            await asyncio.sleep(self._retry_interval)
        async with self._lock:
            now = time.time()
            # Each related limit is represented as it own individual TaskLog
            self._task_logs.append(TaskLog(timestamp=now,
                                           rate_limit=self._rate_limit,
                                           weight=self._rate_limit.weight))
            for limit, weight in self._related_limits:
                task = TaskLog(timestamp=now, rate_limit=limit, weight=weight)
                self._task_logs.append(task)

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        pass
