import asyncio
import copy
import logging
import math
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from hummingbot.core.api_throttler.async_request_context_base import AsyncRequestContextBase
from hummingbot.core.api_throttler.data_types import RateLimit, TaskLog
from hummingbot.logger.logger import HummingbotLogger


class AsyncThrottlerBase(ABC):
    """
    The APIThrottlerBase is an abstract class meant to describe the functions necessary to handle the
    throttling of API requests through the usage of asynchronous context managers.
    """

    # Longest pause we take, whatever the exchange asks for.
    MAX_PAUSE_SECONDS: float = 300.0
    # Shortest and longest pause when the exchange doesn't say how long to wait.
    MIN_DEFAULT_PAUSE_SECONDS: float = 1.0
    MAX_DEFAULT_PAUSE_SECONDS: float = 60.0

    _default_config_map = {}
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
                 limits_share_percentage: Optional[Decimal] = None
                 ):
        """
        :param rate_limits: List of RateLimit(s).
        :param retry_interval: Time between every capacity check.
        :param safety_margin_pct: Percentage of limit to be added as a safety margin when calculating capacity to ensure
            calls are within the limit.
        :param limits_share_percentage: Percentage of the limits to be used by this instance (important when multiple
            bots operate with the same account)
        """
        # If configured, users can define the percentage of rate limits to allocate to the throttler.
        share_percentage = limits_share_percentage or Decimal("100")
        self.limits_pct: Decimal = share_percentage / 100

        self.set_rate_limits(rate_limits)

        # List of TaskLog used to determine the API requests within a set time window.
        self._task_logs: List[TaskLog] = []

        # Throttler Parameters
        self._retry_interval: float = retry_interval
        self._safety_margin_pct: float = safety_margin_pct

        # Shared asyncio.Lock instance to prevent multiple async ContextManager from accessing the _task_logs variable
        self._lock = asyncio.Lock()

        # When each limit_id can be used again. Set when the exchange answers 429.
        self._resets: Dict[str, float] = {}

    def set_rate_limits(self, rate_limits: List[RateLimit]):
        # Rate Limit Definitions
        self._rate_limits: List[RateLimit] = copy.deepcopy(rate_limits)

        for rate_limit in self._rate_limits:
            rate_limit.limit = max(Decimal("1"), math.floor(Decimal(str(rate_limit.limit)) * self.limits_pct))

        # Dictionary of path_url to RateLimit
        self._id_to_limit_map: Dict[str, RateLimit] = {limit.limit_id: limit for limit in self._rate_limits}

    def add_rate_limits(self, rate_limits: List[RateLimit]):
        """
        Dynamically add new rate limits to the throttler.
        Useful when adding trading pairs at runtime that require pair-specific rate limits.

        :param rate_limits: List of RateLimit(s) to add.
        """
        for rate_limit in rate_limits:
            # Skip if already exists
            if rate_limit.limit_id in self._id_to_limit_map:
                continue
            # Apply the limits percentage
            new_limit = copy.deepcopy(rate_limit)
            new_limit.limit = max(Decimal("1"), math.floor(Decimal(str(new_limit.limit)) * self.limits_pct))
            self._rate_limits.append(new_limit)
            self._id_to_limit_map[new_limit.limit_id] = new_limit

    def _client_config_map(self):
        from hummingbot.client.hummingbot_application import HummingbotApplication  # avoids circular import

        return HummingbotApplication.main_application().client_config_map

    def get_related_limits(self, limit_id: str) -> Tuple[RateLimit, List[Tuple[RateLimit, int]]]:
        rate_limit: Optional[RateLimit] = self._id_to_limit_map.get(limit_id, None)
        linked_limits: List[RateLimit] = [] if rate_limit is None else rate_limit.linked_limits

        related_limits = [(self._id_to_limit_map[limit_weight_pair.limit_id], limit_weight_pair.weight)
                          for limit_weight_pair in linked_limits
                          if limit_weight_pair.limit_id in self._id_to_limit_map]

        # Append self as part of the related_limits
        # if rate_limit is not None:
        #     related_limits.append((rate_limit, rate_limit.weight))
#
        return rate_limit, related_limits

    @abstractmethod
    def execute_task(self, limit_id: str) -> AsyncRequestContextBase:
        raise NotImplementedError

    async def pause_after_too_many_requests(self, limit_id: str, retry_after: Optional[float]):
        """Stop sending requests on `limit_id`, and the limits linked to it, for a while.

        Called when the exchange says we are sending too many requests. By then our count
        and the exchange's count no longer agree, for example because of clock differences,
        another bot using the same account, or a limit the connector doesn't know about.
        If we keep sending at the configured rate we just get more rejections, and many
        exchanges then block us for longer. So we wait as long as the exchange asks.

        Linked limits are paused too. Exchanges usually count these per IP or per account
        (like Binance's request weight), so every endpoint that shares the linked limit
        would be rejected as well, not just the one that got the 429.

        :param limit_id: the limit the rejected request was sent under
        :param retry_after: seconds to wait, as sent by the exchange. If None, wait for the
            limit's own time window (between 1s and 60s), since that is when our count resets.
            If zero or negative, the exchange says the limit has already reset, so don't wait.
        """
        rate_limit, related_limits = self.get_related_limits(limit_id=limit_id)
        if retry_after is None:
            window = rate_limit.time_interval if rate_limit is not None else self.MIN_DEFAULT_PAUSE_SECONDS
            retry_after = min(max(window, self.MIN_DEFAULT_PAUSE_SECONDS), self.MAX_DEFAULT_PAUSE_SECONDS)
        elif retry_after <= 0:
            return
        # Cap the wait so a bad header value can't stop the connector for a very long time.
        retry_after = min(retry_after, self.MAX_PAUSE_SECONDS)
        limit_ids = [limit_id] + [related.limit_id for related, _ in related_limits]
        async with self._lock:
            reset_at = self._time() + retry_after
            extended = []
            for paused_id in limit_ids:
                if reset_at > self._resets.get(paused_id, 0.0):
                    self._resets[paused_id] = reset_at
                    extended.append(paused_id)
            if extended:
                self.logger().warning(
                    f"Rate limited by the exchange on {limit_id}; "
                    f"pausing {', '.join(extended)} for {retry_after:.1f}s."
                )

    def _time(self) -> float:
        return time.time()
