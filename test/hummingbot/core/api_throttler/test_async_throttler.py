import asyncio
import logging
import time
import unittest

from decimal import Decimal

from typing import (
    Dict,
    List,
)

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.core.api_throttler.async_throttler import AsyncRequestContext, AsyncThrottler
from hummingbot.core.api_throttler.async_request_context_base import arc_logger
from hummingbot.core.api_throttler.data_types import RateLimit, TaskLog

from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL


TEST_PATH_URL = "/hummingbot"
TEST_POLL_ID = "TEST"

logging.basicConfig(level=METRICS_LOG_LEVEL)


class AsyncThrottlerUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        cls.rate_limits: List[RateLimit] = [
            RateLimit(limit_id=TEST_POLL_ID, limit=1, time_interval=5.0),
            RateLimit(limit_id=TEST_PATH_URL, limit=1, time_interval=5.0, linked_limits=[TEST_POLL_ID])
        ]

    def setUp(self) -> None:
        super().setUp()
        self.throttler = AsyncThrottler(rate_limits=self.rate_limits)
        self._req_counters: Dict[str, int] = {limit.limit_id: 0 for limit in self.rate_limits}

    def tearDown(self) -> None:
        global_config_map["rate_limits_share_pct"].value = 0
        super().tearDown()

    async def execute_requests(self, no_request: int, limit_id: str, throttler: AsyncThrottler):
        for _ in range(no_request):
            async with throttler.execute_task(limit_id=limit_id):
                self._req_counters[limit_id] += 1

    def test_init_without_rate_limits_share_pct(self):
        self.assertEqual(0.1, self.throttler._retry_interval)
        self.assertEqual(2, len(self.throttler._rate_limits))
        self.assertEqual(1, self.throttler._id_to_limit_map[TEST_POLL_ID].limit)
        self.assertEqual(1, self.throttler._id_to_limit_map[TEST_PATH_URL].limit)

    def test_init_with_rate_limits_share_pct(self):

        rate_share_pct: Decimal = Decimal("55")
        global_config_map["rate_limits_share_pct"].value = rate_share_pct
        expected_limit = Decimal("1") * Decimal("55") / Decimal("100")

        throttler = AsyncThrottler(rate_limits=self.rate_limits)
        self.assertEqual(0.1, throttler._retry_interval)
        self.assertEqual(2, len(throttler._rate_limits))
        self.assertEqual(expected_limit, throttler._id_to_limit_map[TEST_POLL_ID].limit)
        self.assertEqual(expected_limit, throttler._id_to_limit_map[TEST_PATH_URL].limit)

    def test_get_relevant_limits(self):
        self.assertEqual(2, len(self.throttler._rate_limits))

        self.assertEqual(1, len(self.throttler.get_relevant_limits(TEST_POLL_ID)))
        self.assertEqual(2, len(self.throttler.get_relevant_limits(TEST_PATH_URL)))

    def test_flush_empty_task_logs(self):
        # Test: No entries in task_logs to flush
        lock = asyncio.Lock()

        self.assertEqual(0, len(self.throttler._task_logs))
        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limits=self.rate_limits,
                                      lock=lock,
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        context.flush()
        self.assertEqual(0, len(self.throttler._task_logs))

    def test_flush_only_elapsed_tasks_are_flushed(self):
        lock = asyncio.Lock()

        self.throttler._task_logs = [
            TaskLog(timestamp=1.0, rate_limits=self.rate_limits),
            TaskLog(timestamp=time.time(), rate_limits=self.rate_limits)
        ]

        self.assertEqual(2, len(self.throttler._task_logs))
        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limits=self.rate_limits,
                                      lock=lock,
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        context.flush()
        self.assertEqual(1, len(self.throttler._task_logs))

    def test_within_capacity_returns_false(self):
        self.throttler._task_logs.append(TaskLog(timestamp=1.0, rate_limits=self.rate_limits))

        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limits=self.rate_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_pct=self.throttler._safety_margin_pct)

        with self.assertLogs(logger=arc_logger) as log:
            self.assertFalse(context.within_capacity())
            self.assertEqual(1, len(log.output))
            self.assertIn("API rate limit on TEST (1 calls per 5.0s) has almost reached. Number of calls is 1 in the last "
                          "5.0 seconds",
                          log.output[0])

    def test_within_capacity_returns_true(self):
        lock = asyncio.Lock()
        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limits=self.rate_limits,
                                      lock=lock,
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        self.assertTrue(context.within_capacity())

    def test_acquire_appends_to_task_logs(self):
        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limits=self.rate_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        self.ev_loop.run_until_complete(context.acquire())
        self.assertEqual(1, len(self.throttler._task_logs))

    def test_acquire_awaits_when_exceed_capacity(self):
        self.throttler._task_logs.append(TaskLog(timestamp=time.time(), rate_limits=self.rate_limits))
        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limits=self.rate_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(context.acquire(), 1.0)
            )
