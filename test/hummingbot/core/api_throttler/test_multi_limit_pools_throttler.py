import unittest
import asyncio
import random
from typing import List, Dict
import time
import logging
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.core.api_throttler.data_types import CallRateLimit
from hummingbot.core.api_throttler.multi_limit_pool_throttler import MultiLimitPoolsThrottler
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather

logging.basicConfig(level=METRICS_LOG_LEVEL)
PATH_0 = "0"
PATH_A = "A"
PATH_B = "B"
RATE_LIMITS = {
    PATH_0: CallRateLimit(limit_id=PATH_0, limit=10, time_interval=1),
    PATH_A: CallRateLimit(limit_id=PATH_A, limit=2, time_interval=1),
    PATH_B: CallRateLimit(limit_id=PATH_B, limit=5, time_interval=1),
}


class MultiLimitPoolsThrottlerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()
        self.throttler = MultiLimitPoolsThrottler(
            rate_limits=list(RATE_LIMITS.values())
        )
        self._req_counters: Dict[str, int] = {path: 0 for path in RATE_LIMITS}

    async def execute_requests(self, no_request: int, limit_ids: List[str], throttler: MultiLimitPoolsThrottler):
        for _ in range(no_request):
            async with throttler.execute_task(limit_ids=limit_ids):
                for limit_id in limit_ids:
                    self._req_counters[limit_id] += 1

    def test_single_pool_requests_above_limit(self):
        # Test Scenario: API requests sent > Rate Limit

        # Note: We assert a timeout ensuring that the throttler does not wait for the limit interval
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.execute_requests(3, [PATH_0, PATH_A], throttler=self.throttler), timeout=0.5)
            )

        self.assertEqual(2, self._req_counters[PATH_A])
        time.sleep(0.6)
        self.ev_loop.run_until_complete(self.execute_requests(2, [PATH_0, PATH_A], throttler=self.throttler))
        self.assertEqual(4, self._req_counters[PATH_A])

    def test_multi_pool_requests_above_limit(self):
        self.ev_loop.run_until_complete(self.execute_requests(8, [PATH_0], throttler=self.throttler))
        # Note: We assert a timeout ensuring that the throttler does not wait for the limit interval
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.execute_requests(3, [PATH_0, PATH_A], throttler=self.throttler), timeout=0.5)
            )

        self.assertEqual(2, self._req_counters[PATH_A])
        time.sleep(0.6)
        self.ev_loop.run_until_complete(self.execute_requests(2, [PATH_0, PATH_A], throttler=self.throttler))
        self.assertEqual(4, self._req_counters[PATH_A])

    def test_requests_below_limit(self):
        # Test Scenario: API requests sent < Rate Limit
        no_reqs: int = random.randint(1, RATE_LIMITS[PATH_B].limit - 1)

        self.ev_loop.run_until_complete(
            self.execute_requests(no_reqs, [PATH_B], throttler=self.throttler))

        self.assertEqual(no_reqs, self._req_counters[PATH_B])
        self.assertLess(no_reqs, RATE_LIMITS[PATH_B].limit)

    def test_requests_at_limit(self):
        # Test Scenario: API requests sent = Rate Limit
        no_reqs = RATE_LIMITS[PATH_A].limit
        start_time: float = time.time()
        self.ev_loop.run_until_complete(
            self.execute_requests(no_reqs, [PATH_A], throttler=self.throttler))
        elapsed: float = time.time() - start_time
        self.assertLess(elapsed, 0.1)
        self.assertEqual(no_reqs, self._req_counters[PATH_A])

    def test_multi_pool_at_limits(self):
        start_time: float = time.time()
        self.ev_loop.run_until_complete(self.execute_requests(3, [PATH_0], throttler=self.throttler))
        self.ev_loop.run_until_complete(self.execute_requests(2, [PATH_0, PATH_A], throttler=self.throttler))
        self.ev_loop.run_until_complete(self.execute_requests(5, [PATH_0, PATH_B], throttler=self.throttler))
        elapsed: float = time.time() - start_time
        self.assertLess(elapsed, 0.1)
        self.ev_loop.run_until_complete(self.execute_requests(1, [PATH_0, PATH_A], throttler=self.throttler))
        self.assertEqual(3, self._req_counters[PATH_A])
        first_path_a_ts = min(t.timestamp for t in self.throttler._task_logs
                              if PATH_A in (r.limit_id for r in t.rate_limits))
        last_path_a_ts = max(t.timestamp for t in self.throttler._task_logs
                             if PATH_A in (r.limit_id for r in t.rate_limits))
        self.assertTrue(first_path_a_ts + 1 < last_path_a_ts < first_path_a_ts + 1.5)

    def test_async_lock(self):
        self.ev_loop.run_until_complete(self._test_async_lock())

    async def _test_async_lock(self):
        # Make limit to PATH_0 almost full at 9 but can take one more
        await self.execute_requests(7, [PATH_0], throttler=self.throttler)
        await self.execute_requests(2, [PATH_0, PATH_A], throttler=self.throttler)
        # Requests to PATH_A is at limit now, so adding a new one has to wait
        self.assertEqual(2, self._req_counters[PATH_A])
        future_a = safe_ensure_future(self.execute_requests(1, [PATH_0, PATH_A], throttler=self.throttler))
        await asyncio.sleep(0.01)
        self.assertEqual(2, self._req_counters[PATH_A])
        # Adding a PATH_B request at which pool is empty, but bc the above is blocking, it shouldn't be added yet
        future_b = safe_ensure_future(self.execute_requests(1, [PATH_B], throttler=self.throttler))
        await asyncio.sleep(0.01)
        self.assertEqual(2, self._req_counters[PATH_A])
        self.assertEqual(0, self._req_counters[PATH_B])
        await safe_gather(future_a, future_b)
        self.assertEqual(3, self._req_counters[PATH_A])
        self.assertEqual(1, self._req_counters[PATH_B])
        # Check the latest PATH_A and PATH_B items timestamps
        last_path_a_ts = max(t.timestamp for t in self.throttler._task_logs if t.rate_limits[-1].limit_id == PATH_A)
        last_path_b_ts = max(t.timestamp for t in self.throttler._task_logs if t.rate_limits[-1].limit_id == PATH_B)
        self.assertTrue(last_path_b_ts > last_path_a_ts)
