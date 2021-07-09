import unittest
import aiohttp
import asyncio
import random
import requests

from unittest.mock import patch

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.api_throttler.fixed_rate_api_throttler import FixedRateThrottler

from test.hummingbot.core.api_throttler.throttled_mock_server import (
    ThrottledMockServer,
    BASE_URL,
    TEST_PATH_URL,
)

FIXED_RATE_LIMIT = [
    RateLimit(5, 5)
]


class FixedRateThrottlerUnitTests(unittest.TestCase):

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

        cls.mock_server.clear_responses()
        cls.mock_server.update_response(method="GET",
                                        host=BASE_URL,
                                        path=TEST_PATH_URL,
                                        data=cls.mock_server.TEST_RESPONSE,
                                        is_json=False
                                        )

    @classmethod
    def tearDownClass(cls):
        cls.mock_server.stop()
        cls._patcher.stop()
        cls._req_patcher.stop()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()

        self.mock_server.reset_request_count()

        self.fixed_rate_throttler = FixedRateThrottler(rate_limit_list=FIXED_RATE_LIMIT,
                                                       retry_interval=5.0)

    async def execute_n_requests(self, n: int, throttler: FixedRateThrottler):
        for _ in range(n):
            async with throttler.execute_task():
                async with aiohttp.ClientSession() as client:
                    await client.get(f"https://{BASE_URL + TEST_PATH_URL}")

    def test_fixed_rate_throttler_above_limit(self):
        # Test Scenario: API requests sent > Rate Limit
        n: int = 10
        limit: int = FIXED_RATE_LIMIT[0].limit

        # Note: We assert a timeout ensuring that the throttler does not wait for the limit interval
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.execute_n_requests(n, throttler=self.fixed_rate_throttler), timeout=1.0)
            )

        self.assertEqual(limit, self.mock_server.request_count)

    def test_fixed_rate_throttler_below_limit(self):
        # Test Scenario: API requests sent < Rate Limit
        n: int = random.randint(1, FIXED_RATE_LIMIT[0].limit - 1)
        limit: int = FIXED_RATE_LIMIT[0].limit

        self.ev_loop.run_until_complete(
            self.execute_n_requests(n, throttler=self.fixed_rate_throttler))

        self.assertEqual(self.mock_server.request_count, n)
        self.assertLess(self.mock_server.request_count, limit)

    def test_fixed_rate_throttler_equal_limit(self):
        # Test Scenario: API requests sent = Rate Limit
        n = limit = FIXED_RATE_LIMIT[0].limit

        self.ev_loop.run_until_complete(
            self.execute_n_requests(n, throttler=self.fixed_rate_throttler))

        self.assertEqual(self.mock_server.request_count, limit)
