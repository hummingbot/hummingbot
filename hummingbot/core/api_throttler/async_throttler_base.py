import asyncio
import copy
import logging
import math

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import (
    Dict,
    List,
    Optional,
    Tuple,
)

from hummingbot.core.api_throttler.async_request_context_base import AsyncRequestContextBase
from hummingbot.core.api_throttler.data_types import (
    RateLimit,
    TaskLog
)
from hummingbot.logger.logger import HummingbotLogger


class AsyncThrottlerBase(ABC):
    """
    The APIThrottlerBase is an abstract class meant to describe the functions necessary to handle the
    throttling of API requests through the usage of asynchronous context managers.
    """

    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 rate_limits: List[RateLimit],
                 retry_interval: float = 0.1,
                 safety_margin_pct: Optional[float] = 0.05,  # An extra safety margin, in percentage.
                 ):
        """
        :param rate_limits: List of RateLimit(s).
        :param retry_interval: Time between every capacity check.
        :param safety_margin: Percentage of limit to be added as a safety margin when calculating capacity to ensure calls are within the limit.
        """
        from hummingbot.client.config.global_config_map import global_config_map  # avoids chance of circular import

        # Rate Limit Definitions
        self._rate_limits: List[RateLimit] = copy.deepcopy(rate_limits)
        limits_pct_conf: Optional[Decimal] = global_config_map["rate_limits_share_pct"].value

        # If configured, users can define the percentage of rate limits to allocate to the throttler.
        self.limits_pct: Optional[Decimal] = Decimal("1") if limits_pct_conf is None else limits_pct_conf / Decimal("100")
        for rate_limit in self._rate_limits:
            rate_limit.limit = max(Decimal("1"),
                                   math.floor(Decimal(str(rate_limit.limit)) * self.limits_pct))

        # Dictionary of path_url to RateLimit
        self._id_to_limit_map: Dict[str, RateLimit] = {
            limit.limit_id: limit
            for limit in self._rate_limits
        }

        # List of TaskLog used to determine the API requests within a set time window.
        self._task_logs: List[TaskLog] = []

        # Throttler Parameters
        self._retry_interval: float = retry_interval
        self._safety_margin_pct: float = safety_margin_pct

        # Shared asyncio.Lock instance to prevent multiple async ContextManager from accessing the _task_logs variable
        self._lock = asyncio.Lock()

    def get_related_limits(self, limit_id: str) -> Tuple[RateLimit, List[Tuple[RateLimit, int]]]:
        rate_limit: Optional[RateLimit] = self._id_to_limit_map.get(limit_id, None)

        related_limits = [(self._id_to_limit_map[limit_weight_pair.limit_id], limit_weight_pair.weight)
                          for limit_weight_pair in rate_limit.linked_limits
                          if limit_weight_pair.limit_id in self._id_to_limit_map]
        # Append self as part of the related_limits
        related_limits.append((rate_limit, rate_limit.weight))

        return rate_limit, related_limits

    @abstractmethod
    def execute_task(self, limit_ids: List[str]) -> AsyncRequestContextBase:
        raise NotImplementedError
