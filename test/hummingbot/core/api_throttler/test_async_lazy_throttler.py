import asyncio
import logging
import math
from asyncio import wait_for
from decimal import Decimal
from typing import Dict, List
from unittest.mock import patch

from aiounittest import AsyncTestCase

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.core.api_throttler.async_request_context_base import AsyncRequestContextBase
from hummingbot.core.api_throttler.async_throttler import AsyncRequestContext, AsyncThrottler
from hummingbot.core.api_throttler.data_types import LimiterMethod, LinkedLimitWeightPair, TokenBucket
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL

TEST_PATH_URL = "/hummingbot"
TEST_POOL_ID = "TEST"
TEST_WEIGHTED_POOL_ID = "TEST_WEIGHTED"
TEST_WEIGHTED_TASK_1_ID = "/weighted_task_1"
TEST_WEIGHTED_TASK_2_ID = "/weighted_task_2"

logging.basicConfig(level=METRICS_LOG_LEVEL)


class AsyncLazyThrottlerUnitTests(AsyncTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        cls.rate_limits: List[TokenBucket] = [
            TokenBucket(limit_id=TEST_POOL_ID,
                        capacity=1,
                        rate_per_s=0.2,
                        is_fill=True),
            TokenBucket(limit_id=TEST_PATH_URL,
                        capacity=1,
                        rate_per_s=0.2,
                        is_fill=True,
                        linked_limits=[LinkedLimitWeightPair(TEST_POOL_ID)]),
            TokenBucket(limit_id=TEST_WEIGHTED_POOL_ID,
                        capacity=10,
                        rate_per_s=2,
                        is_fill=True),
            TokenBucket(limit_id=TEST_WEIGHTED_TASK_1_ID,
                        capacity=1000,
                        rate_per_s=200,
                        is_fill=True,
                        linked_limits=[LinkedLimitWeightPair(TEST_WEIGHTED_POOL_ID, 5)]),
            TokenBucket(limit_id=TEST_WEIGHTED_TASK_2_ID,
                        capacity=1000,
                        rate_per_s=200,
                        is_fill=True,
                        linked_limits=[LinkedLimitWeightPair(TEST_WEIGHTED_POOL_ID, 1)]),
        ]

    def setUp(self) -> None:
        AsyncRequestContextBase._token_bucket = dict()
        AsyncRequestContextBase._last_max_cap_warning_ts = Decimal("0")
        self.throttler = AsyncThrottler(rate_limits=self.rate_limits)
        self._req_counters: Dict[str, int] = {limit.limit_id: 0 for limit in self.rate_limits}
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.log_records = []
        self.data_feed = self.throttler
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    @classmethod
    def tearDown(self) -> None:
        pass

    def handle(self, record):
        self.log_records.append(record)

    def is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and record.getMessage() == message for
            record in self.log_records)

    async def execute_requests(self, no_request: int, limit_id: str, throttler: AsyncThrottler):
        for _ in range(no_request):
            async with throttler.execute_task(limit_id=limit_id):
                self._req_counters[limit_id] += 1

    def test_init_without_rate_limits_share_pct(self):
        self.assertEqual(Decimal("0.1"), self.throttler._retry_interval)
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
        rate_limits.append(TokenBucket(limit_id="ANOTHER_TEST", capacity=10, rate_per_s=2, is_fill=True))
        expected_limit = math.floor(Decimal("2") * rate_share_pct / Decimal("100"))
        expected_capacity = math.floor(Decimal("10") * rate_share_pct / Decimal("100"))

        throttler = AsyncThrottler(rate_limits=rate_limits)
        self.assertEqual(Decimal("0.1"), throttler._retry_interval)
        self.assertEqual(6, len(throttler._rate_limits))
        self.assertEqual(Decimal("1"), throttler._id_to_limit_map[TEST_POOL_ID].limit)
        self.assertEqual(Decimal("1"), throttler._id_to_limit_map[TEST_PATH_URL].limit)
        self.assertEqual(expected_limit, throttler._id_to_limit_map["ANOTHER_TEST"].limit)
        self.assertEqual(expected_capacity, throttler._id_to_limit_map["ANOTHER_TEST"].capacity)

    def test_get_related_limits(self):
        self.assertEqual(5, len(self.throttler._rate_limits))

        _, related_limits = self.throttler.get_related_limits(TEST_POOL_ID)
        self.assertEqual(1, len(related_limits))

        _, related_limits = self.throttler.get_related_limits(TEST_PATH_URL)
        self.assertEqual(2, len(related_limits))

    def test_within_capacity_singular_non_weighted_task_returns_false(self):
        rate_limit, _ = self.throttler.get_related_limits(limit_id=TEST_POOL_ID)

        context = AsyncRequestContext(task_logs=[],
                                      rate_limit=rate_limit,
                                      related_limits=[(rate_limit, rate_limit.weight)],
                                      lock=asyncio.Lock(),
                                      safety_margin_as_fraction=self.throttler._safety_margin_as_fraction,
                                      method=LimiterMethod.FILL_TOKEN_BUCKET
                                      )
        self.assertTrue(context.within_capacity())
        self.assertFalse(context.within_capacity())

    def test_within_capacity_singular_non_weighted_task_returns_true(self):
        rate_limit, _ = self.throttler.get_related_limits(limit_id=TEST_POOL_ID)
        context = AsyncRequestContext(task_logs=[],
                                      rate_limit=rate_limit,
                                      related_limits=[(rate_limit, rate_limit.weight)],
                                      lock=asyncio.Lock(),
                                      safety_margin_as_fraction=self.throttler._safety_margin_as_fraction,
                                      method=LimiterMethod.FILL_TOKEN_BUCKET
                                      )
        self.assertTrue(context.within_capacity())

    def test_within_capacity_pool_non_weighted_task_returns_false(self):
        rate_limit, related_limits = self.throttler.get_related_limits(limit_id=TEST_PATH_URL)

        context = AsyncRequestContext(task_logs=[],
                                      rate_limit=rate_limit,
                                      related_limits=related_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_as_fraction=self.throttler._safety_margin_as_fraction,
                                      method=LimiterMethod.FILL_TOKEN_BUCKET
                                      )
        self.assertTrue(context.within_capacity())

        context = AsyncRequestContext(task_logs=[],
                                      rate_limit=rate_limit,
                                      related_limits=related_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_as_fraction=self.throttler._safety_margin_as_fraction,
                                      method=LimiterMethod.FILL_TOKEN_BUCKET,
                                      token_buckets=context.token_buckets
                                      )
        self.assertFalse(context.within_capacity())

    def test_within_capacity_pool_non_weighted_task_returns_true(self):
        rate_limit, related_limits = self.throttler.get_related_limits(limit_id=TEST_PATH_URL)

        context = AsyncRequestContext(task_logs=[],
                                      rate_limit=rate_limit,
                                      related_limits=related_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_as_fraction=self.throttler._safety_margin_as_fraction,
                                      method=LimiterMethod.FILL_TOKEN_BUCKET
                                      )
        self.assertTrue(context.within_capacity())

    def test_within_capacity_pool_weighted_tasks(self):
        task_1, task_1_related_limits = self.throttler.get_related_limits(limit_id=TEST_WEIGHTED_TASK_1_ID)

        # Simulate Weighted Task 1 and Task 2 already in task logs, resulting in a used capacity of 6/10
        context = AsyncRequestContext(task_logs=[],
                                      rate_limit=task_1,
                                      related_limits=task_1_related_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_as_fraction=self.throttler._safety_margin_as_fraction,
                                      method=LimiterMethod.FILL_TOKEN_BUCKET,
                                      )
        self.assertTrue(context.within_capacity())

        task_2, task_2_related_limits = self.throttler.get_related_limits(limit_id=TEST_WEIGHTED_TASK_2_ID)
        context = AsyncRequestContext(task_logs=[],
                                      rate_limit=task_2,
                                      related_limits=task_2_related_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_as_fraction=self.throttler._safety_margin_as_fraction,
                                      method=LimiterMethod.FILL_TOKEN_BUCKET,
                                      token_buckets=context.token_buckets
                                      )
        self.assertTrue(context.within_capacity())

        # Another Task 1(weight=5) will exceed the capacity(11/10)
        context = AsyncRequestContext(task_logs=[],
                                      rate_limit=task_1,
                                      related_limits=task_1_related_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_as_fraction=self.throttler._safety_margin_as_fraction,
                                      method=LimiterMethod.FILL_TOKEN_BUCKET,
                                      token_buckets=context.token_buckets
                                      )
        self.assertFalse(context.within_capacity())

        # However Task 2(weight=1) will not exceed the capacity(7/10)
        context = AsyncRequestContext(task_logs=[],
                                      rate_limit=task_2,
                                      related_limits=task_2_related_limits,
                                      lock=asyncio.Lock(),
                                      safety_margin_as_fraction=self.throttler._safety_margin_as_fraction,
                                      method=LimiterMethod.FILL_TOKEN_BUCKET,
                                      token_buckets=context.token_buckets
                                      )
        self.assertTrue(context.within_capacity())

    def test_within_capacity_returns_true(self):
        lock = asyncio.Lock()
        rate_limit = self.rate_limits[0]
        context = AsyncRequestContext(task_logs=[],
                                      rate_limit=rate_limit,
                                      related_limits=[(rate_limit, rate_limit.weight)],
                                      lock=lock,
                                      safety_margin_as_fraction=self.throttler._safety_margin_as_fraction,
                                      method=LimiterMethod.FILL_TOKEN_BUCKET
                                      )
        self.assertTrue(context.within_capacity())

    async def test_acquire_does_not_append_to_task_logs(self):
        rate_limit = self.rate_limits[0]
        context = AsyncRequestContext(task_logs=[],
                                      rate_limit=rate_limit,
                                      related_limits=[(rate_limit, rate_limit.weight)],
                                      lock=asyncio.Lock(),
                                      safety_margin_as_fraction=self.throttler._safety_margin_as_fraction,
                                      method=LimiterMethod.FILL_TOKEN_BUCKET
                                      )
        await context.acquire()
        self.assertEqual(0, len(self.throttler._task_logs))

    async def test_acquire_awaits_when_exceed_capacity(self):
        rate_limit = self.rate_limits[0]
        context = AsyncRequestContext(task_logs=[],
                                      rate_limit=rate_limit,
                                      related_limits=[(rate_limit, rate_limit.weight)],
                                      lock=asyncio.Lock(),
                                      safety_margin_as_fraction=self.throttler._safety_margin_as_fraction,
                                      method=LimiterMethod.FILL_TOKEN_BUCKET
                                      )
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.assertTrue(context.within_capacity())
            await wait_for(context.acquire(), 1.0)

    def test_within_capacity_returns_true_for_throttler_without_configured_limits(self):
        throttler = AsyncThrottler(rate_limits=[])
        context = throttler.execute_task(limit_id="test_limit_id")
        self.assertTrue(context.within_capacity())

    @patch("hummingbot.core.api_throttler.async_throttler.time_counter_in_s")
    def test_within_capacity_for_throttler_with_burst_limit(self, time_mock):
        per_second_limit = TokenBucket(limit_id="generic_per_second", capacity=3, rate_per_s=1)
        log = "API rate limit on generic_per_second (1 calls per 1s) is almost reached. The current request is being " \
              "rate limited (it will execute after a delay)"
        context = AsyncRequestContext(
            task_logs=[],
            rate_limit=per_second_limit,
            related_limits=[(per_second_limit, 1)],
            lock=asyncio.Lock(),
            safety_margin_as_fraction=0,
            method=LimiterMethod.FILL_TOKEN_BUCKET
        )
        time_mock.side_effect = (Decimal("1640000000.0000"),
                                 Decimal("1640000000.0000"),
                                 Decimal("1640000000.0000"),
                                 # No more burst capacity
                                 Decimal("1640000000.0000"),
                                 # Almost time
                                 Decimal("1640000000.9999"),
                                 # Refill time
                                 Decimal("1640000001.0000"),
                                 # Refilled only one token
                                 Decimal("1640000001.0000"),
                                 # Accumulated enough to burst, 3s burst + 1s beyond max
                                 Decimal("1640000005.0000"),
                                 Decimal("1640000005.0000"),
                                 Decimal("1640000005.0000"),
                                 Decimal("1640000005.0000"),
                                 )

        # 3 tasks requested, Burst capacity: 3, t: 0s
        self.assertTrue(context.within_capacity())
        self.assertTrue(context.within_capacity())
        self.assertTrue(context.within_capacity())

        self.assertFalse(self.is_logged(log_level="INFO", message=log))

        # One additional task, Burst capacity: 3, t: 0s -> No more capacity
        self.assertFalse(context.within_capacity())

        # Rate limit is reached
        self.assertTrue(self.is_logged(log_level="INFO", message=log))

        # 3 tasks executed, Burst capacity: 3, t: 0.9999s -> still no cap
        self.assertFalse(context.within_capacity())

        # 3 tasks executed, Burst capacity: 3, t: 1s -> only 1 new capacity
        self.assertTrue(context.within_capacity())
        self.assertFalse(context.within_capacity())

        # 3 tasks executed, Burst capacity: 3, t: 5s -> Accumulated enough, let's burst 3, but no more
        self.assertTrue(context.within_capacity())
        self.assertTrue(context.within_capacity())
        self.assertTrue(context.within_capacity())
        self.assertFalse(context.within_capacity())

    @patch("hummingbot.core.api_throttler.async_throttler.time_counter_in_s")
    def test_within_capacity_for_throttler_burst_limit_with_task_weight(self, time_mock):
        per_second_limit = TokenBucket(limit_id="generic_per_second", capacity=3, rate_per_s=1)
        log = "API rate limit on generic_per_second (1 calls per 1s) is almost reached. The current request is being " \
              "rate limited (it will execute after a delay)"
        context = AsyncRequestContext(
            task_logs=[],
            rate_limit=per_second_limit,
            related_limits=[(per_second_limit, 3)],
            lock=asyncio.Lock(),
            safety_margin_as_fraction=0,
            method=LimiterMethod.FILL_TOKEN_BUCKET,
        )
        time_mock.return_value = (Decimal("1640000000.0000"))
        self.assertTrue(context.within_capacity())
        self.assertFalse(self.is_logged(log_level="INFO", message=log))
        self.assertFalse(context.within_capacity())
        self.assertTrue(self.is_logged(log_level="INFO", message=log))
