import unittest
import asyncio
import random

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.api_throttler.varied_rate_api_throttler import VariedRateThrottler

TEST_PATH_URL = "TEST_PATH_URL"
VARIED_RATE_LIMIT = [
    RateLimit(5, 5, TEST_PATH_URL)
]


class VariedRateAPIThrottler(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()
        self.varied_rate_throttler = VariedRateThrottler(rate_limit_list=VARIED_RATE_LIMIT,
                                                         retry_interval=5.0)
        self.request_count = 0

    async def execute_n_requests(self, n: int, throttler: VariedRateThrottler):
        for _ in range(n):
            async with throttler.execute_task(path_url=TEST_PATH_URL):
                self.request_count += 1

    def test_varied_rate_throttler_above_limit(self):
        # Test Scenario: API requests sent > Rate Limit
        n: int = 10
        limit: int = VARIED_RATE_LIMIT[0].limit

        # Note: We assert a timeout ensuring that the throttler does not wait for the limit interval
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.execute_n_requests(n, throttler=self.varied_rate_throttler), timeout=1.0)
            )

        self.assertEqual(limit, self.request_count)

    def test_varied_rate_throttler_below_limit(self):
        # Test Scenario: API requests sent < Rate Limit
        n: int = random.randint(1, VARIED_RATE_LIMIT[0].limit - 1)
        limit: int = VARIED_RATE_LIMIT[0].limit

        self.ev_loop.run_until_complete(
            self.execute_n_requests(n, throttler=self.varied_rate_throttler))

        self.assertEqual(self.request_count, n)
        self.assertLess(self.request_count, limit)

    def test_varied_rate_throttler_equal_limit(self):
        # Test Scenario: API requests sent = Rate Limit
        n = limit = VARIED_RATE_LIMIT[0].limit

        self.ev_loop.run_until_complete(
            self.execute_n_requests(n, throttler=self.varied_rate_throttler))

        self.assertEqual(self.request_count, limit)
