import unittest
import aiohttp
import asyncio
import random
import requests

from aiohttp import web
from unittest.mock import patch
from typing import (
    List,
)

from hummingbot.core.mock_api.mock_web_server import MockWebServer
from hummingbot.core.utils.api_throttler import APIThrottler, RateLimit, RateLimitType

BASE_URL = "www.hbottesst.com"


WEIGHTED_PATH_URL = "/test_weighted"
PER_METHOD_PATH_URL = "/test_per_method"

FIXED_RATE_LIMIT = [
    RateLimit(100, 1)
]

WEIGHTED_RATE_LIMIT = [
    RateLimit(100, 10, WEIGHTED_PATH_URL, 2)
]

PER_METHOD_RATE_LIMIT = [
    RateLimit(5, 1, PER_METHOD_PATH_URL)
]


class ThrottledMockServer(MockWebServer):

    def __init__(self):
        super().__init__()
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
                                        path=PER_METHOD_PATH_URL,
                                        data=cls.mock_server.TEST_RESPONSE,
                                        is_json=False
                                        )

    def setUp(self) -> None:
        super().setUp()

        self.per_method_rate_throttler = APIThrottler(rate_limit_list=PER_METHOD_RATE_LIMIT,
                                                      rate_limit_type=RateLimitType.PER_METHOD,
                                                      retry_interval=5.0)

        # self.fixed_rate_throttler = APIThrottler()
        # self.weighted_rate_throttler = APIThrottler()

    @classmethod
    def tearDownClass(cls):
        cls.mock_server.stop()
        cls._patcher.stop()
        cls._req_patcher.stop()
        super().tearDownClass()

    async def execute_n_per_method_requests(self, n: int, throttler: APIThrottler, message_queue: List[str]):
        for _ in range(n):
            async with throttler.per_method_task(path_url=PER_METHOD_PATH_URL):
                async with aiohttp.ClientSession() as client:
                    async with client.get(f"https://{BASE_URL + PER_METHOD_PATH_URL}") as resp:
                        data: str = await resp.text()
                        message_queue.append(data)

    def test_per_method_rate_throttler_above_limit(self):
        # Test Scenario: API requests sent > Rate Limit
        n: int = 10
        result_message: List[str] = []

        # Note that we assert a timeout; ensuring that the throttler does not wait for the limit interval
        with self.assertRaises(asyncio.exceptions.TimeoutError):
            self.ev_loop.run_until_complete(
                asyncio.wait_for(
                    self.execute_n_per_method_requests(n,
                                                       throttler=self.per_method_rate_throttler,
                                                       message_queue=result_message),
                    timeout=1.0))
        self.assertEqual(len(result_message), PER_METHOD_RATE_LIMIT[0].limit)

    def test_per_method_rate_throttler_below_limit(self):
        # Test Scenario: API requests sent < Rate Limit
        n: int = random.randint(1, PER_METHOD_RATE_LIMIT[0].limit - 1)
        result_message: List[str] = []
        self.ev_loop.run_until_complete(asyncio.wait_for(
            self.execute_n_per_method_requests(n,
                                               throttler=self.per_method_rate_throttler,
                                               message_queue=result_message),
            timeout=1.0))

        self.assertLessEqual(len(result_message), PER_METHOD_RATE_LIMIT[0].limit)

    def test_per_method_rate_throttler_equal_limit(self):
        # Test Scenario: API requests sent = Rate Limit
        n: int = 5
        result_message: List[str] = []
        self.ev_loop.run_until_complete(asyncio.wait_for(
            self.execute_n_per_method_requests(n,
                                               throttler=self.per_method_rate_throttler,
                                               message_queue=result_message),
            timeout=1.0))

        self.assertEqual(len(result_message), PER_METHOD_RATE_LIMIT[0].limit)
