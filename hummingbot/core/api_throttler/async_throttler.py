import logging
import time
from decimal import Decimal
from math import floor
from typing import Callable, List

from hummingbot.core.api_throttler.async_request_context_base import (
    MAX_CAPACITY_REACHED_WARNING_INTERVAL,
    AsyncRequestContextBase,
    _T_Bucket,
)
from hummingbot.core.api_throttler.async_throttler_base import AsyncThrottlerBase
from hummingbot.core.api_throttler.data_types import (
    LimiterMethod,
    RateLimit,
    TaskLog,
    TokenBucket,
    _T_Capacity,
    _T_Rate,
    _T_RequestPath,
    _T_RequestWeight,
    _T_Seconds,
)
from hummingbot.logger import HummingbotLogger

ONE: Decimal = Decimal("1")


def time_counter_in_s() -> _T_Seconds:
    return _T_Seconds(time.perf_counter())


class AsyncRequestContext(AsyncRequestContextBase):
    """
    An async context class ('async with' syntax) that checks for rate limit and wait for the capacity if needed.
    It uses async lock to prevent other instances of this class from running acquire fn before it finishes with it.
    """

    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def _flush(self, now: _T_Seconds):
        """
        Remove task logs that have passed rate limit periods for the Sliding window method
        """
        for task in self._task_logs:
            elapsed: _T_Seconds = now - task.timestamp
            task_interval: _T_Seconds = task.rate_limit.time_interval
            if elapsed > task_interval * (1 + self._safety_margin_as_fraction):
                self._task_logs.remove(task)

    def _accept_request(self, now: _T_Seconds):
        """
        Updates the bucket for a weighted Leaky or Fill Token Bucket algorithm
            (https://en.m.wikipedia.org/wiki/Token_bucket)
        as well as the sliding window capacity calculation

        2. Consume/Replenish weighted tokens for the current request
        """
        limit_id: _T_RequestPath = self._rate_limit.limit_id
        weight: _T_RequestWeight = self._rate_limit.weight

        if self._method == LimiterMethod.FILL_TOKEN_BUCKET:
            amount: _T_Bucket = self._token_bucket[limit_id]
            amount['amount']: _T_RequestWeight = amount['amount'] - weight

        elif self._method == LimiterMethod.LEAK_TOKEN_BUCKET:
            amount: _T_Bucket = self._token_bucket[limit_id]
            amount['amount']: _T_RequestWeight = amount['amount'] + weight

        elif self._method == LimiterMethod.SLIDING_WINDOW:
            self._task_logs.append(TaskLog(timestamp=now, rate_limit=self._rate_limit, weight=self._rate_limit.weight))
            for limit, weight in self._related_limits:
                self._task_logs.append(TaskLog(timestamp=now, rate_limit=limit, weight=weight))

    def _check_rate_limit_capacity(self, rate_limit: RateLimit, now: _T_Seconds) -> int:
        """
        Implements the bucket update for a weighted Leaky or Fill Token Bucket algorithm
            (https://en.m.wikipedia.org/wiki/Token_bucket)
        as well as the sliding window capacity calculation

        1. Leak/Fill the user's TokenBucket to a token size based on the following formula:
           token_amount = max(burst, previous_token_amount -/+ (current_time - previous_request_time) * refresh_rate)
        :param rate_limit: Rate limit for the current request
        :returns: Available capacity
        :rtype: int
        """
        capacity: _T_Capacity = rate_limit.capacity if hasattr(rate_limit, "capacity") else _T_Capacity(rate_limit.limit)
        rate_per_s: _T_Rate = rate_limit.rate_per_s if hasattr(rate_limit, "rate_per_s") else _T_Rate(ONE)
        limit_id: _T_RequestPath = rate_limit.limit_id

        if self._method in (LimiterMethod.LEAK_TOKEN_BUCKET, LimiterMethod.FILL_TOKEN_BUCKET):
            if limit_id not in self._token_bucket:
                amount: int = capacity if self._method == LimiterMethod.FILL_TOKEN_BUCKET else 0
                self._token_bucket[limit_id]: _T_Bucket = dict(amount=amount, last_checked=Decimal("-1"))

            bucket: _T_Bucket = self._token_bucket[limit_id]

            if (tokens := floor((now - bucket['last_checked']) * rate_per_s)) >= 1:
                bucket['last_checked']: _T_Seconds = now

            if self._method == LimiterMethod.LEAK_TOKEN_BUCKET:
                bucket['amount']: _T_Capacity = max(0, bucket['amount'] - tokens)
                return capacity - bucket['amount']

            elif self._method == LimiterMethod.FILL_TOKEN_BUCKET:
                bucket['amount']: _T_Capacity = min(capacity, bucket['amount'] + tokens)
                return bucket['amount']

        elif self._method == LimiterMethod.SLIDING_WINDOW:
            safety: Decimal = Decimal(self._safety_margin_as_fraction)
            tasks_log: List[TaskLog] = self._task_logs

            is_id: Callable[[int], bool] = lambda x: x == limit_id
            is_wd: Callable[[...], bool] = lambda x, y: now - x <= Decimal(y) * (ONE + safety)
            capacity_used: int = sum([t.weight
                                      for t in tasks_log
                                      if is_id((tr := t.rate_limit).limit_id) and
                                      is_wd(t.timestamp, tr.time_interval)])
            return capacity - capacity_used

        else:
            return None

    def within_capacity(self) -> bool:
        """
        Checks if an additional task within the defined RateLimit(s). Logs a warning message if the limit is about to be
        reached.
        Note: A task can be associated to one or more RateLimit.
        :return: True if it is within capacity to add a new task
        """
        now: _T_Seconds = time_counter_in_s()
        if self._method == LimiterMethod.SLIDING_WINDOW:
            self._flush(now)

        if len(self._related_limits) > 0:
            for rate_limit, weight in self._related_limits:
                capacity: int = self._check_rate_limit_capacity(rate_limit, now)

                if weight > capacity:
                    if self._last_max_cap_warning_ts < now - MAX_CAPACITY_REACHED_WARNING_INTERVAL:
                        msg = f"API rate limit on {rate_limit.limit_id} ({rate_limit.limit} calls per " \
                              f"{rate_limit.time_interval}s) is almost reached. The current request " \
                              "is being rate limited (it will execute after a delay)"
                        self.logger().notify(msg)
                        AsyncRequestContextBase._last_max_cap_warning_ts = now
                    return False
            self._accept_request(now)
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
        this (whether it belongs to Pool 0 or Pool 1) will have to wait for new capacity (some Task A flushed out).
    """

    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def execute_task(self, limit_id: str) -> AsyncRequestContext:
        """
        Creates an async context where code within the context (a task) can be run only when all rate
        limits have capacity for the new task.
        :param limit_id: the limit_id associated with the API request
        :return: An async context (used with async with syntax)
        """
        rate_limit, related_rate_limits = self.get_related_limits(limit_id=limit_id)
        method: LimiterMethod = LimiterMethod.SLIDING_WINDOW
        if isinstance(rate_limit, TokenBucket):
            if rate_limit.is_fill:
                method: LimiterMethod = LimiterMethod.FILL_TOKEN_BUCKET
            else:
                method: LimiterMethod = LimiterMethod.LEAK_TOKEN_BUCKET

        return AsyncRequestContext(
            task_logs=self._task_logs,
            rate_limit=rate_limit,
            related_limits=related_rate_limits,
            lock=self._lock,
            safety_margin_as_fraction=self._safety_margin_as_fraction,
            retry_interval=self._retry_interval,
            method=method
        )
