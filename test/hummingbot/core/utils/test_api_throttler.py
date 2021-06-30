import unittest
import aiohttp
import asyncio
import random
import requests

from aiohttp import web
from unittest.mock import patch

from hummingbot.core.mock_api.mock_web_server import MockWebServer
from hummingbot.core.utils.api_throttler import APIThrottler, RateLimit, RateLimitType

BASE_URL = "www.hbottesst.com"


TEST_PATH_URL = "/test"

FIXED_RATE_LIMIT = [
    RateLimit(5, 5)
]

WEIGHTED_RATE_LIMIT = [
    RateLimit(5, 5, TEST_PATH_URL, 2)
]

PER_METHOD_RATE_LIMIT = [
    RateLimit(5, 5, TEST_PATH_URL)
]


class ThrottledMockServer(MockWebServer):

    def __init__(self):
        super().__init__()
        self._request_count = 0

    @property
    def request_count(self) -> int:
        return self._request_count

    def reset_request_count(self):
        self._request_count = 0

    async def _handler(self, request: web.Request):
        self._request_count += 1
        return await super()._handler(request)


class APIThrottlerUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        cls.mock_server = ThrottledMockServer()
        cls.mock_server.add_host_to_mock(BASE_URL)

        cls.mock_server.start()
        cls.ev_loop.run_until_complete(cls.mock_server.wait_til_started())

        cls._patcher = patch("aiohttp.client.URL")
        cls._url_mock = cls._patcher.start()
        cls._url_mock.side_effect = MockWebServer.reroute_local

        cls._req_patcher = unittest.mock.patch.object(requests.Session, "request", autospec=True)
        cls._req_url_mock = cls._req_patcher.start()
        cls._req_url_mock.side_effect = MockWebServer.reroute_request

        cls.mock_server.clear_responses()
        cls.mock_server.update_response(method="GET",
                                        host=BASE_URL,
                                        path=TEST_PATH_URL,
                                        data=cls.mock_server.TEST_RESPONSE,
                                        is_json=False
                                        )

    def setUp(self) -> None:
        super().setUp()

        self.mock_server.reset_request_count()

        self.per_method_rate_throttler = APIThrottler(rate_limit_list=PER_METHOD_RATE_LIMIT,
                                                      rate_limit_type=RateLimitType.PER_METHOD,
                                                      retry_interval=5.0)

        self.fixed_rate_throttler = APIThrottler(rate_limit_list=FIXED_RATE_LIMIT,
                                                 rate_limit_type=RateLimitType.FIXED,
                                                 retry_interval=5.0)

        self.weighted_rate_throttler = APIThrottler(rate_limit_list=WEIGHTED_RATE_LIMIT,
                                                    rate_limit_type=RateLimitType.WEIGHTED,
                                                    retry_interval=5.0)

    @classmethod
    def tearDownClass(cls):
        cls.mock_server.stop()
        cls._patcher.stop()
        cls._req_patcher.stop()
        super().tearDownClass()

    async def execute_n_per_method_requests(self, n: int, throttler: APIThrottler):
        for _ in range(n):
            async with throttler.per_method_task(path_url=TEST_PATH_URL):
                async with aiohttp.ClientSession() as client:
                    await client.get(f"https://{BASE_URL + TEST_PATH_URL}")

    async def execute_n_fixed_requests(self, n: int, throttler: APIThrottler):
        for _ in range(n):
            async with throttler.fixed_rate_task():
                async with aiohttp.ClientSession() as client:
                    await client.get(f"https://{BASE_URL + TEST_PATH_URL}")

    async def execute_n_weighted_requests(self, n: int, throttler: APIThrottler):
        for _ in range(n):
            async with throttler.weighted_task(path_url=TEST_PATH_URL):
                async with aiohttp.ClientSession() as client:
                    await client.get(f"https://{BASE_URL + TEST_PATH_URL}")

    def test_per_method_rate_throttler_above_limit(self):
        # Test Scenario: API requests sent > Rate Limit
        n: int = 10
        limit: int = PER_METHOD_RATE_LIMIT[0].limit

        # Note: We assert a timeout ensuring that the throttler does not wait for the limit interval
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.execute_n_per_method_requests(n, throttler=self.per_method_rate_throttler), timeout=1.0)
            )

        self.assertEqual(limit, self.mock_server.request_count)

    def test_per_method_rate_throttler_below_limit(self):
        # Test Scenario: API requests sent < Rate Limit
        n: int = random.randint(1, PER_METHOD_RATE_LIMIT[0].limit - 1)
        limit: int = PER_METHOD_RATE_LIMIT[0].limit

        self.ev_loop.run_until_complete(
            self.execute_n_per_method_requests(n, throttler=self.per_method_rate_throttler))

        self.assertEqual(self.mock_server.request_count, n)
        self.assertLess(self.mock_server.request_count, limit)

    def test_per_method_rate_throttler_equal_limit(self):
        # Test Scenario: API requests sent = Rate Limit
        n = limit = PER_METHOD_RATE_LIMIT[0].limit

        self.ev_loop.run_until_complete(
            self.execute_n_per_method_requests(n, throttler=self.per_method_rate_throttler))

        self.assertEqual(self.mock_server.request_count, limit)

    def test_fixed_rate_throttler_above_limit(self):
        # Test Scenario: API requests sent > Rate Limit
        n: int = 10
        limit: int = FIXED_RATE_LIMIT[0].limit

        # Note: We assert a timeout ensuring that the throttler does not wait for the limit interval
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.execute_n_fixed_requests(n, throttler=self.fixed_rate_throttler), timeout=1.0)
            )

        self.assertEqual(limit, self.mock_server.request_count)

    def test_fixed_rate_throttler_below_limit(self):
        # Test Scenario: API requests sent < Rate Limit
        n: int = random.randint(1, FIXED_RATE_LIMIT[0].limit - 1)
        limit: int = FIXED_RATE_LIMIT[0].limit

        self.ev_loop.run_until_complete(
            self.execute_n_fixed_requests(n, throttler=self.fixed_rate_throttler))

        self.assertEqual(self.mock_server.request_count, n)
        self.assertLess(self.mock_server.request_count, limit)

    def test_fixed_rate_throttler_equal_limit(self):
        # Test Scenario: API requests sent = Rate Limit
        n = limit = FIXED_RATE_LIMIT[0].limit

        self.ev_loop.run_until_complete(
            self.execute_n_fixed_requests(n, throttler=self.fixed_rate_throttler))

        self.assertEqual(self.mock_server.request_count, limit)

    def test_weighted_rate_throttler_above_limit(self):
        # Test Scenario: API requests sent > Rate Limit
        n: int = 10
        limit: int = WEIGHTED_RATE_LIMIT[0].limit
        weight: int = WEIGHTED_RATE_LIMIT[0].weight

        expected_request_count: int = limit // weight

        # Note: We assert a timeout ensuring that the throttler does not wait for the limit interval
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(self.execute_n_weighted_requests(n, throttler=self.weighted_rate_throttler), timeout=1.0)
            )

        self.assertEqual(expected_request_count, self.mock_server.request_count)

    def test_weighted_rate_throttler_below_limit(self):
        n: int = WEIGHTED_RATE_LIMIT[0].limit // WEIGHTED_RATE_LIMIT[0].weight

        self.ev_loop.run_until_complete(
            self.execute_n_weighted_requests(n, throttler=self.weighted_rate_throttler))

        self.assertEqual(n, self.mock_server.request_count)

    def test_weighted_rate_throttler_equal_limit(self):
        rate_limit: RateLimit = RateLimit(5, 5, TEST_PATH_URL, 1)

        n: int = rate_limit.limit // rate_limit.weight

        self.weighted_rate_throttler = APIThrottler(rate_limit_list=[rate_limit],
                                                    rate_limit_type=RateLimitType.WEIGHTED,
                                                    retry_interval=5.0)

        self.ev_loop.run_until_complete(
            self.execute_n_weighted_requests(n, throttler=self.weighted_rate_throttler))

        self.assertEqual(n, self.mock_server.request_count)
