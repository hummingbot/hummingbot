import unittest
import asyncio

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.api_throttler.weighted_api_throttler import WeightedAPIThrottler

TEST_PATH_URL = "TEST_PATH_URL"
WEIGHTED_RATE_LIMIT = [
    RateLimit(5, 5, TEST_PATH_URL, 2)
]


class WeightedAPIThrottlerUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()
        self.weighted_rate_throttler = WeightedAPIThrottler(rate_limit_list=WEIGHTED_RATE_LIMIT,
                                                            retry_interval=5.0)
        self.request_count = 0

    async def execute_n_requests(self, n: int, throttler: WeightedAPIThrottler):
        for _ in range(n):
            async with throttler.execute_task(path_url=TEST_PATH_URL):
                self.request_count += 1

    def test_weighted_rate_throttler_above_limit(self):
        # Test Scenario: API requests sent > Rate Limit
        n: int = 10
        limit: int = WEIGHTED_RATE_LIMIT[0].limit
        weight: int = WEIGHTED_RATE_LIMIT[0].weight

        expected_request_count: int = limit // weight

        # Note: We assert a timeout ensuring that the throttler does not wait for the limit interval
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.execute_n_requests(n, throttler=self.weighted_rate_throttler), timeout=1.0)
            )

        self.assertEqual(expected_request_count, self.request_count)

    def test_weighted_rate_throttler_below_limit(self):
        n: int = WEIGHTED_RATE_LIMIT[0].limit // WEIGHTED_RATE_LIMIT[0].weight

        self.ev_loop.run_until_complete(
            self.execute_n_requests(n, throttler=self.weighted_rate_throttler))

        self.assertEqual(n, self.request_count)

    def test_weighted_rate_throttler_equal_limit(self):
        rate_limit: RateLimit = WEIGHTED_RATE_LIMIT[0]

        n: int = rate_limit.limit // rate_limit.weight

        self.ev_loop.run_until_complete(
            self.execute_n_requests(n, throttler=self.weighted_rate_throttler))

        self.assertEqual(n, self.request_count)
