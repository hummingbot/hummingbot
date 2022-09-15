import asyncio
import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Tuple, Union

from hummingbot.core.api_throttler.data_types import (
    LimiterMethod,
    TaskLog,
    _T_Capacity,
    _T_RateToken,
    _T_RequestPath,
    _T_RequestWeight,
    _T_Seconds,
)
from hummingbot.logger.logger import HummingbotLogger

arc_logger = None
MAX_CAPACITY_REACHED_WARNING_INTERVAL = Decimal("30.0")

_T_Bucket = Dict[_T_RequestPath, Union[_T_Capacity, Decimal]]
_T_Buckets = Dict[_T_RequestPath, _T_Bucket]


class AsyncRequestContextBase(ABC):
    """
    An async context class ('async with' syntax) that checks for rate limit and waits for the capacity to be freed.
    It uses an async lock to prevent multiple instances of this class from accessing the `acquire()` function.
    """

    _last_max_cap_warning_ts: _T_Seconds = _T_Seconds("0")

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global arc_logger
        if arc_logger is None:
            arc_logger = logging.getLogger(__name__)
        return arc_logger

    __slots__ = (
        '_task_logs',
        '_rate_limit',
        '_related_limits',
        '_lock',
        '_safety_margin_as_fraction',
        '_retry_interval',
        '_method',
    )

    def __init__(self,
                 task_logs: List[TaskLog],
                 rate_limit: _T_RateToken,
                 related_limits: List[Tuple[_T_RateToken, _T_RequestWeight]],
                 lock: asyncio.Lock,
                 safety_margin_as_fraction: Union[_T_Seconds, float] = _T_Seconds("0.05"),
                 retry_interval: Union[_T_Seconds, float] = _T_Seconds("0.1"),
                 method: LimiterMethod = LimiterMethod.SLIDING_WINDOW
                 ):
        """
        Asynchronous context associated with each API request.
        :param task_logs: Shared task logs associated with this API request
        :param rate_limit: The RateLimit associated with this API Request
        :param related_limits: List of linked rate limits with its corresponding weight associated with this API Request
        :param lock: A shared asyncio.Lock used between all instances of APIRequestContextBase
        :param retry_interval: Time between each limit check
        :param method: Method used to apply rate limits
        """
        self._task_logs: List[TaskLog] = task_logs
        self._rate_limit: _T_RateToken = rate_limit
        self._related_limits: List[Tuple[_T_RateToken, _T_RequestWeight]] = related_limits
        self._lock: asyncio.Lock = lock
        self._safety_margin_as_fraction: _T_Seconds = _T_Seconds(safety_margin_as_fraction)
        self._retry_interval: _T_Seconds = _T_Seconds(retry_interval)
        self._method: LimiterMethod = method

        self._token_bucket: _T_Buckets = dict()

    @abstractmethod
    def within_capacity(self) -> bool:
        raise NotImplementedError

    async def acquire(self):
        while True:
            async with self._lock:

                if self.within_capacity():
                    break
            await asyncio.sleep(float(self._retry_interval))

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        pass
