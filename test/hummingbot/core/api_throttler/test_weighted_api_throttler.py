import unittest
import aiohttp
import asyncio
import requests

from unittest.mock import patch

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.api_throttler.weighted_api_throttler import WeightedAPIThrottler

from test.hummingbot.core.api_throttler.throttled_mock_server import (
    ThrottledMockServer,
    BASE_URL,
    TEST_PATH_URL,
)

WEIGHTED_RATE_LIMIT = [
    RateLimit(5, 5, TEST_PATH_URL, 2)
]


class WeightedAPIThrottlerUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        cls.mock_server = ThrottledMockServer.get_instance()
        cls.mock_server.add_host_to_mock(BASE_URL)
        cls.mock_server.start()
        cls.ev_loop.run_until_complete(cls.mock_server.wait_til_started())

        cls._patcher = patch("aiohttp.client.URL")
        cls._url_mock = cls._patcher.start()
        cls._url_mock.side_effect = ThrottledMockServer.reroute_local

        cls._req_patcher = unittest.mock.patch.object(requests.Session, "request", autospec=True)
        cls._req_url_mock = cls._req_patcher.start()
        cls._req_url_mock.side_effect = ThrottledMockServer.reroute_request

    @classmethod
    def tearDownClass(cls):
        cls.mock_server.stop()
        cls._patcher.stop()
        cls._req_patcher.stop()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()

        self.mock_server.reset_request_count()

        self.weighted_rate_throttler = WeightedAPIThrottler(rate_limit_list=WEIGHTED_RATE_LIMIT,
                                                            retry_interval=5.0)

    async def execute_n_requests(self, n: int, throttler: WeightedAPIThrottler):
        for _ in range(n):
            async with throttler.execute_task(path_url=TEST_PATH_URL):
                async with aiohttp.ClientSession() as client:
                    await client.get(f"https://{BASE_URL + TEST_PATH_URL}")

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

        self.assertEqual(expected_request_count, self.mock_server.request_count)

    def test_weighted_rate_throttler_below_limit(self):
        n: int = WEIGHTED_RATE_LIMIT[0].limit // WEIGHTED_RATE_LIMIT[0].weight

        self.ev_loop.run_until_complete(
            self.execute_n_requests(n, throttler=self.weighted_rate_throttler))

        self.assertEqual(n, self.mock_server.request_count)

    def test_weighted_rate_throttler_equal_limit(self):
        rate_limit: RateLimit = WEIGHTED_RATE_LIMIT[0]

        n: int = rate_limit.limit // rate_limit.weight

        self.ev_loop.run_until_complete(
            self.execute_n_requests(n, throttler=self.weighted_rate_throttler))

        self.assertEqual(n, self.mock_server.request_count)
