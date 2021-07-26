import asyncio
import time
import unittest
import logging
from typing import List
from decimal import Decimal
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.core.api_throttler.multi_limit_pool_throttler import (
    mlpt_logger,
    MultiLimitPoolsThrottler,
    MultiLimitPoolsRequestContext,
)
from hummingbot.core.api_throttler.data_types import CallRateLimit, MultiLimitsTaskLog
from hummingbot.client.config.global_config_map import global_config_map

logging.basicConfig(level=METRICS_LOG_LEVEL)


class MultiLimitPoolsThrottlerBasicUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        cls.rate_limits: List[CallRateLimit] = [
            CallRateLimit(limit_id="A", limit=10, time_interval=5.0)
        ]

    def setUp(self) -> None:
        super().setUp()
        self.throttler = MultiLimitPoolsThrottler(rate_limits=self.rate_limits)

    def test_init(self):
        global_config_map["rate_limits_share_pct"].value = Decimal("55")
        throttler = MultiLimitPoolsThrottler(rate_limits=self.rate_limits)
        self.assertEqual(0.1, throttler._retry_interval)
        self.assertEqual(1, len(throttler._rate_limits))
        self.assertEqual(5, throttler._rate_limits[0].limit)

    def test_flush(self):

        # Test: No Task Logs to flush
        lock = asyncio.Lock()
        context = MultiLimitPoolsRequestContext(self.throttler._task_logs, self.rate_limits, lock)
        context._flush()

        self.assertEqual(0, len(self.throttler._task_logs))

        # Test: Test that TaskLogs are being flushed accordingly.
        task_0 = MultiLimitsTaskLog(timestamp=1.0, rate_limits=self.rate_limits)
        task_1 = MultiLimitsTaskLog(timestamp=time.time() + 60, rate_limits=self.rate_limits)
        self.throttler._task_logs.append(task_0)
        self.throttler._task_logs.append(task_1)
        self.assertEqual(2, len(self.throttler._task_logs))

        context = MultiLimitPoolsRequestContext(self.throttler._task_logs, self.rate_limits, lock)
        context._flush()

    def test_within_capacity(self):
        limits = [CallRateLimit(limit_id="A", limit=1, time_interval=5.0)]
        MultiLimitPoolsRequestContext._last_max_cap_warning_ts = 0
        lock = asyncio.Lock()
        context = MultiLimitPoolsRequestContext(self.throttler._task_logs, limits, lock)
        self.assertTrue(context._within_capacity())
        task_1 = MultiLimitsTaskLog(timestamp=time.time() - 1., rate_limits=limits)
        self.throttler._task_logs.append(task_1)
        context = MultiLimitPoolsRequestContext(self.throttler._task_logs, limits, lock)
        with self.assertLogs(logger=mlpt_logger) as log:
            self.assertFalse(context._within_capacity())
            self.assertEqual(1, len(log.output))
            self.assertIn("API rate limit on A (1 calls per 5.0s) has almost reached. Number of calls is 1 in the last "
                          "5.0 seconds",
                          log.output[0])

    def test_task_appended_after_acquire(self):
        context = MultiLimitPoolsRequestContext(self.throttler._task_logs, self.rate_limits, asyncio.Lock())
        self.ev_loop.run_until_complete(context._acquire())
        self.assertEqual(1, len(self.throttler._task_logs))

    def test_acquire_awaits_when_exceed_capacity(self):
        limits = [CallRateLimit(limit_id="A", limit=1, time_interval=5.0)]
        task_1 = MultiLimitsTaskLog(timestamp=time.time(), rate_limits=limits)
        self.throttler._task_logs.append(task_1)

        context = MultiLimitPoolsRequestContext(self.throttler._task_logs, limits, asyncio.Lock())
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(context._acquire(), 1.0)
            )
