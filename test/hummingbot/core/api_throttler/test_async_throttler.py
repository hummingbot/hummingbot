import asyncio
import logging
import math
import sys
import time
import unittest
from decimal import Decimal
from typing import Dict, List
from unittest.mock import patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.core.api_throttler.async_throttler import AsyncRequestContext, AsyncThrottler
from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit, TaskLog
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL

TEST_PATH_URL = "/hummingbot"
TEST_POOL_ID = "TEST"
TEST_WEIGHTED_POOL_ID = "TEST_WEIGHTED"
TEST_WEIGHTED_TASK_1_ID = "/weighted_task_1"
TEST_WEIGHTED_TASK_2_ID = "/weighted_task_2"

logging.basicConfig(level=METRICS_LOG_LEVEL)


class AsyncThrottlerUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        cls.rate_limits: List[RateLimit] = [
            RateLimit(limit_id=TEST_POOL_ID, limit=1, time_interval=5.0),
            RateLimit(limit_id=TEST_PATH_URL, limit=1, time_interval=5.0,
                      linked_limits=[LinkedLimitWeightPair(TEST_POOL_ID)]),
            RateLimit(limit_id=TEST_WEIGHTED_POOL_ID, limit=10, time_interval=5.0),
            RateLimit(limit_id=TEST_WEIGHTED_TASK_1_ID,
                      limit=1000,
                      time_interval=5.0,
                      linked_limits=[LinkedLimitWeightPair(TEST_WEIGHTED_POOL_ID, 5)]),
            RateLimit(limit_id=TEST_WEIGHTED_TASK_2_ID,
                      limit=1000,
                      time_interval=5.0,
                      linked_limits=[LinkedLimitWeightPair(TEST_WEIGHTED_POOL_ID, 1)]),
        ]

    def setUp(self) -> None:
        super().setUp()
        self.throttler = AsyncThrottler(rate_limits=self.rate_limits)
        self._req_counters: Dict[str, int] = {limit.limit_id: 0 for limit in self.rate_limits}
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())

    async def execute_requests(self, no_request: int, limit_id: str, throttler: AsyncThrottler):
        for _ in range(no_request):
            async with throttler.execute_task(limit_id=limit_id):
                self._req_counters[limit_id] += 1

    def test_init_without_rate_limits_share_pct(self):
        self.assertEqual(0.1, self.throttler._retry_interval)
        self.assertEqual(5, len(self.throttler._rate_limits))
        self.assertEqual(1, self.throttler._id_to_limit_map[TEST_POOL_ID].limit)
        self.assertEqual(1, self.throttler._id_to_limit_map[TEST_PATH_URL].limit)

    @patch("hummingbot.core.api_throttler.async_throttler_base.AsyncThrottlerBase._client_config_map")
    def test_init_with_rate_limits_share_pct(self, config_map_mock):

        rate_share_pct: Decimal = Decimal("55")
        self.client_config_map.rate_limits_share_pct = rate_share_pct
        config_map_mock.return_value = self.client_config_map
        self.throttler = AsyncThrottler(rate_limits=self.rate_limits)

        rate_limits = self.rate_limits.copy()
        rate_limits.append(RateLimit(limit_id="ANOTHER_TEST", limit=10, time_interval=5))
        expected_limit = math.floor(Decimal("10") * rate_share_pct / Decimal("100"))

        throttler = AsyncThrottler(rate_limits=rate_limits)
        self.assertEqual(0.1, throttler._retry_interval)
        self.assertEqual(6, len(throttler._rate_limits))
        self.assertEqual(Decimal("1"), throttler._id_to_limit_map[TEST_POOL_ID].limit)
        self.assertEqual(Decimal("1"), throttler._id_to_limit_map[TEST_PATH_URL].limit)
        self.assertEqual(expected_limit, throttler._id_to_limit_map["ANOTHER_TEST"].limit)

    def test_get_related_limits(self):
        self.assertEqual(5, len(self.throttler._rate_limits))

        rate_limit, related_limits = self.throttler.get_related_limits(TEST_POOL_ID)
        self.assertEqual(TEST_POOL_ID, rate_limit.limit_id)
        self.assertEqual(0, len(related_limits))

        rate_limit, related_limits = self.throttler.get_related_limits(TEST_PATH_URL)
        self.assertEqual(TEST_PATH_URL, rate_limit.limit_id)
        self.assertEqual(1, len(related_limits))

    def test_flush_empty_task_logs(self):
        # Test: No entries in task_logs to flush
        lock = asyncio.Lock()

        rate_limit = self.rate_limits[0]
        self.assertEqual(0, len(self.throttler._task_logs))
        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limit=rate_limit,
                                      related_limits=[(rate_limit, rate_limit.weight)],
                                      lock=lock,
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        context.flush()
        self.assertEqual(0, len(self.throttler._task_logs))

    def test_flush_only_elapsed_tasks_are_flushed(self):
        lock = asyncio.Lock()
        rate_limit = self.rate_limits[0]
        self.throttler._task_logs = [
            TaskLog(timestamp=1.0, rate_limit=rate_limit, weight=rate_limit.weight),
            TaskLog(timestamp=time.time(), rate_limit=rate_limit, weight=rate_limit.weight)
        ]

        self.assertEqual(2, len(self.throttler._task_logs))
        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limit=rate_limit,
                                      related_limits=[(rate_limit, rate_limit.weight)],
                                      lock=lock,
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        context.flush()
        self.assertEqual(1, len(self.throttler._task_logs))

    def test_within_capacity_singular_non_weighted_task_returns_false(self):
        rate_limit, _ = self.throttler.get_related_limits(limit_id=TEST_POOL_ID)
        self.throttler._task_logs.append(
            TaskLog(timestamp=time.time(), rate_limit=rate_limit, weight=rate_limit.weight))

        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limit=rate_limit,
                                      related_limits=[(rate_limit, rate_limit.weight)],
                                      lock=asyncio.Lock(),
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        self.assertFalse(context.within_capacity())

    def test_within_capacity_singular_non_weighted_task_returns_true(self):
        rate_limit, _ = self.throttler.get_related_limits(limit_id=TEST_POOL_ID)
        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limit=rate_limit,
                                      related_limits=[(rate_limit, rate_limit.weight)],
                                      lock=asyncio.Lock(),
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        self.assertTrue(context.within_capacity())

    def test_within_capacity_pool_non_weighted_task_returns_false(self):
        rate_limit, related_limits = self.throttler.get_related_limits(limit_id=TEST_PATH_URL)

        for linked_limit, weight in related_limits:
            self.throttler._task_logs.append(TaskLog(timestamp=time.time(), rate_limit=linked_limit, weight=weight))

        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limit=rate_limit,
                                      related_limits=related_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        self.assertFalse(context.within_capacity())

    def test_within_capacity_pool_non_weighted_task_returns_true(self):
        rate_limit, related_limits = self.throttler.get_related_limits(limit_id=TEST_PATH_URL)

        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limit=rate_limit,
                                      related_limits=related_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        self.assertTrue(context.within_capacity())

    def test_within_capacity_pool_weighted_tasks(self):
        task_1, task_1_related_limits = self.throttler.get_related_limits(limit_id=TEST_WEIGHTED_TASK_1_ID)

        # Simulate Weighted Task 1 and Task 2 already in task logs, resulting in a used capacity of 6/10
        for linked_limit, weight in task_1_related_limits:
            self.throttler._task_logs.append(TaskLog(timestamp=time.time(), rate_limit=linked_limit, weight=weight))
        task_2, task_2_related_limits = self.throttler.get_related_limits(limit_id=TEST_WEIGHTED_TASK_2_ID)
        for linked_limit, weight in task_2_related_limits:
            self.throttler._task_logs.append(TaskLog(timestamp=time.time(), rate_limit=linked_limit, weight=weight))

        # Another Task 1(weight=5) will exceed the capacity(11/10)
        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limit=task_1,
                                      related_limits=task_1_related_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        self.assertFalse(context.within_capacity())

        # However Task 2(weight=1) will not exceed the capacity(7/10)
        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limit=task_2,
                                      related_limits=task_2_related_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        self.assertTrue(context.within_capacity())

    def test_within_capacity_returns_true(self):
        lock = asyncio.Lock()
        rate_limit = self.rate_limits[0]
        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limit=rate_limit,
                                      related_limits=[(rate_limit, rate_limit.weight)],
                                      lock=lock,
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        self.assertTrue(context.within_capacity())

    def test_acquire_appends_to_task_logs(self):
        rate_limit = self.rate_limits[0]
        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limit=rate_limit,
                                      related_limits=[],
                                      lock=asyncio.Lock(),
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        self.ev_loop.run_until_complete(context.acquire())

        # We acquire()'d just one rate_limit, task log should have only one entry
        self.assertEqual(1, len(self.throttler._task_logs))

    def test_acquire_awaits_when_exceed_capacity(self):
        rate_limit = self.rate_limits[0]
        self.throttler._task_logs.append(
            TaskLog(timestamp=time.time(), rate_limit=rate_limit, weight=rate_limit.weight))
        context = AsyncRequestContext(task_logs=self.throttler._task_logs,
                                      rate_limit=rate_limit,
                                      related_limits=[(rate_limit, rate_limit.weight)],
                                      lock=asyncio.Lock(),
                                      safety_margin_pct=self.throttler._safety_margin_pct)
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(context.acquire(), 1.0)
            )

    def test_within_capacity_returns_true_for_throttler_without_configured_limits(self):
        throttler = AsyncThrottler(rate_limits=[])
        context = throttler.execute_task(limit_id="test_limit_id")
        self.assertTrue(context.within_capacity())

    @patch("hummingbot.core.api_throttler.async_throttler.AsyncRequestContext._time")
    def test_within_capacity_for_limits_with_milliseconds_interval(self, time_mock):
        per_second_limit = RateLimit(limit_id="generic_per_second", limit=3, time_interval=1)
        per_millisecond_limit = RateLimit(limit_id="generic_per_millisecond", limit=2, time_interval=0.2)
        specific_limit = RateLimit(limit_id="specific_limit", limit=sys.maxsize, time_interval=1, linked_limits=[
            LinkedLimitWeightPair(per_second_limit.limit_id),
            LinkedLimitWeightPair(per_millisecond_limit.limit_id),
        ])

        # Scenario where one specific task was executed at 0 milliseconds
        tasks_log = []
        tasks_log.append(TaskLog(timestamp=1640000000.0000, rate_limit=per_millisecond_limit, weight=1))
        tasks_log.append(TaskLog(timestamp=1640000000.0000, rate_limit=per_second_limit, weight=1))

        context = AsyncRequestContext(
            task_logs=tasks_log,
            rate_limit=specific_limit,
            related_limits=[(per_millisecond_limit, 1), (per_second_limit, 1), (specific_limit, 1)],
            lock=asyncio.Lock(),
            safety_margin_pct=0,
        )

        time_mock.return_value = 1640000000.0100
        result = context.within_capacity()
        self.assertTrue(result)

        # Add one more occurrence of the same task but at millisecond 1
        tasks_log.append(TaskLog(timestamp=1640000000.1000, rate_limit=per_millisecond_limit, weight=1))
        tasks_log.append(TaskLog(timestamp=1640000000.1000, rate_limit=per_second_limit, weight=1))

        time_mock.return_value = 1640000000.1000
        result = context.within_capacity()
        self.assertFalse(result)

        time_mock.return_value = 1640000000.1900
        result = context.within_capacity()
        self.assertFalse(result)

        time_mock.return_value = 1640000000.2000
        result = context.within_capacity()
        self.assertFalse(result)

        time_mock.return_value = 1640000000.2100
        result = context.within_capacity()
        self.assertTrue(result)
