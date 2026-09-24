import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import List, Tuple

from hummingbot.core.api_throttler.data_types import RateLimit, TaskLog
from hummingbot.logger.logger import HummingbotLogger

arc_logger = None
MAX_CAPACITY_REACHED_WARNING_INTERVAL = 30.0


class AsyncRequestContextBase(ABC):
    """
    An async context class ('async with' syntax) that checks for rate limit and waits for the capacity to be freed.
    It uses an async lock to prevent multiple instances of this class from accessing the `acquire()` function.
    """

    _last_max_cap_warning_ts: float = 0.0

    # Max seconds a request that hasn't finished can keep its slot. Stops a task that
    # never gets marked complete from blocking the limit forever. Kept above aiohttp's
    # default total timeout (300s) so a REST call that is still open keeps its slot.
    IN_FLIGHT_HOLD_LIMIT: float = 330.0

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
        :param related_limits: List of linked rate limits with its corresponding weight associated with this API Request
        :param lock: A shared asyncio.Lock used between all instances of APIRequestContextBase
        :param retry_interval: Time between each limit check
        """
        self._task_logs: List[TaskLog] = task_logs
        self._rate_limit: RateLimit = rate_limit
        self._related_limits: List[Tuple[RateLimit, int]] = related_limits
        self._lock: asyncio.Lock = lock
        self._safety_margin_pct: float = safety_margin_pct
        self._retry_interval: float = retry_interval
        # Task logs added by this request, so we can mark them complete when it finishes.
        self._own_tasks: List[TaskLog] = []

    def flush(self):
        """
        Remove task logs whose rate limit window has passed.

        A request that hasn't finished yet keeps its slot even after the window passes.
        Otherwise, when responses are slow, more and more requests pile up at the
        exchange at the same time.

        Unfinished tasks are still removed after IN_FLIGHT_HOLD_LIMIT seconds, in case
        one is never marked complete.
        """
        now: float = time.time()
        retained = []
        for task in self._task_logs:
            age = now - task.timestamp
            window = task.rate_limit.time_interval * (1 + self._safety_margin_pct)
            if age <= window or (not task.completed and age <= self.IN_FLIGHT_HOLD_LIMIT):
                retained.append(task)
            elif not task.completed:
                self.logger().warning(
                    f"Freeing a rate limit slot for {task.rate_limit.limit_id} held for {age:.0f}s "
                    f"by a request that never finished."
                )
        self._task_logs[:] = retained

    @abstractmethod
    def within_capacity(self) -> bool:
        raise NotImplementedError

    async def acquire(self):
        while True:
            async with self._lock:
                self.flush()

                if self.within_capacity():
                    # Record the task under the same lock hold as the capacity check
                    self._log_acquired_task()
                    return
            await asyncio.sleep(self._retry_interval)

    def _log_acquired_task(self):
        now = time.time()
        # Each related limit is represented as it own individual TaskLog

        # Log the acquired rate limit into the tasks log
        new_logs = [
            TaskLog(timestamp=now, rate_limit=self._rate_limit, weight=self._rate_limit.weight,
                    completed=False)
        ] + [
            # Log its related limits into the tasks log as individual tasks
            TaskLog(timestamp=now, rate_limit=limit, weight=weight, completed=False)
            for limit, weight in self._related_limits
        ]
        self._task_logs.extend(new_logs)
        self._own_tasks = new_logs

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        # The request is done (or failed or was cancelled), so free its slots.
        # No lock needed: setting a flag can't be interrupted. Waiting for the lock here
        # could get cancelled and leave the slot held until IN_FLIGHT_HOLD_LIMIT.
        for task in self._own_tasks:
            task.completed = True
