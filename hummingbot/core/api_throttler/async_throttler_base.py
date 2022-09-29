import asyncio
import copy
import logging
import math
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union

from hummingbot.core.api_throttler.async_request_context_base import AsyncRequestContextBase
from hummingbot.core.api_throttler.data_types import (
    RateLimit,
    TaskLog,
    TokenBucket,
    _T_Buckets,
    _T_RateToken,
    _T_Seconds,
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

    __slots__ = (
        '_rate_limits',
        'limits_in_pct',
        '_id_to_limit_map',
        '_task_logs',
        '_token_buckets',
        '_retry_interval',
        '_safety_margin_as_fraction',
        '_lock',
    )

    def __init__(self,
                 rate_limits: List[RateLimit],
                 retry_interval: Union[_T_Seconds, float] = _T_Seconds("0.1"),
                 safety_margin_pct: Optional[float] = 5,  # An extra safety margin, in percentage
                 limits_share_percentage: Optional[Decimal] = Decimal("100")
                 ):
        """
        :param rate_limits: List of RateLimit(s).
        :param retry_interval: Time between every capacity check.
        :param safety_margin_pct: Percentage of limit to be added as a safety margin when calculating capacity to ensure calls are within the limit.
        :param limits_share_percentage: Percentage of the limits to be used by this instance (important when multiple
            bots operate with the same account)
        """
        # Rate Limit Definitions
        self._rate_limits: List[RateLimit] = copy.deepcopy(rate_limits)

        # If configured, users can define the percentage of rate limits to allocate to the throttler.
        self.limits_in_pct: Decimal = min(limits_share_percentage,
                                          self._client_config_map().rate_limits_share_pct) / Decimal("100")
        for rate_limit in self._rate_limits:
            if isinstance(rate_limit, TokenBucket):
                rate_limit.capacity = max(1, math.floor(rate_limit.capacity * self.limits_in_pct))
                rate_limit.limit = max(1, math.floor(rate_limit.limit * self.limits_in_pct))
            else:
                rate_limit.limit = max(1, math.floor(rate_limit.limit * self.limits_in_pct))

        # Dictionary of path_url to RateLimit
        self._id_to_limit_map: Dict[str, _T_RateToken] = {
            limit.limit_id: limit
            for limit in self._rate_limits
        }

        # List of TaskLog used to determine the API requests within a set time window.
        self._task_logs: List[TaskLog] = []

        # Buckets for Token Bucket algorithm.
        self._token_buckets: _T_Buckets = {}

        # Throttler Parameters
        self._retry_interval: _T_Seconds = _T_Seconds(retry_interval)
        self._safety_margin_as_fraction: Decimal = Decimal(safety_margin_pct) * Decimal("0.01")

        # Shared asyncio.Lock instance to prevent multiple async ContextManager from accessing the _task_logs variable
        self._lock = asyncio.Lock()

    def _client_config_map(self):
        from hummingbot.client.hummingbot_application import HummingbotApplication  # avoids circular import
        return HummingbotApplication.main_application().client_config_map

    def get_related_limits(self, limit_id: str) -> Tuple[_T_RateToken, List[Tuple[_T_RateToken, int]]]:
        rate_limit: Optional[_T_RateToken] = self._id_to_limit_map.get(limit_id, None)
        linked_limits: List[_T_RateToken] = [] if rate_limit is None else rate_limit.linked_limits

        related_limits = [(self._id_to_limit_map[limit_weight_pair.limit_id], limit_weight_pair.weight)
                          for limit_weight_pair in linked_limits if limit_weight_pair.limit_id in self._id_to_limit_map]
        # Append self as part of the related_limits
        if rate_limit is not None:
            related_limits.append((rate_limit, rate_limit.weight))

        return rate_limit, related_limits

    @abstractmethod
    def execute_task(self, limit_id: str) -> AsyncRequestContextBase:
        raise NotImplementedError
