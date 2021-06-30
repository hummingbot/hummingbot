import unittest
import aiohttp
import asyncio
import requests

from unittest.mock import patch
from aiohttp import web

from hummingbot.core.mock_api.mock_web_server import MockWebServer
from hummingbot.core.utils.api_throttler import APIThrottler, RateLimitType

BASE_URL = "http://127.0.0.1"

TEST_PATH_URL = "/test"

FIXED_RATE_LIMIT = (100, 1)

WEIGHTED_RATE_LIMIT = {
    "/test_weighted": (100, 2, 10)  # Limit 100/10sec, weight: 2
}

PER_METHOD_RATE_LIMIT = {
    "/test_per_method": (100, 10)
}


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

        cls.port = cls.mock_server.port

        cls._patcher = patch("aiohttp.client.URL")
        cls._url_mock = cls._patcher.start()
        cls._url_mock.side_effect = MockWebServer.reroute_local

        cls._req_patcher = unittest.mock.patch.object(requests.Session, "request", autospec=True)
        cls._req_url_mock = cls._req_patcher.start()
        cls._req_url_mock.side_effect = MockWebServer.reroute_request

        # cls.fixed_rate_throttler = APIThrottler()
        # cls.weighted_rate_throttler = APIThrottler()

        cls.per_method_rate_throttler = APIThrottler(rate_limit=PER_METHOD_RATE_LIMIT,
                                                     rate_limit_type=RateLimitType.PER_METHOD)

    @classmethod
    def tearDownClass(cls):
        cls.mock_server.stop()
        cls._patcher.stop()
        cls._req_patcher.stop()
        super().tearDownClass()

    async def execute_requests(self, n: int, throttler: APIThrottler):
        for _ in range(n):
            if throttler.rate_limit_type == RateLimitType.PER_METHOD:
                async with throttler.per_method_task(path_url="/test_per_method"):
                    async with aiohttp.ClientSession() as client:
                        async with client.get(f"{BASE_URL}:{self.port}/test_per_method") as resp:
                            text: str = await resp.text()
                            print(text)

    def test_per_method_rate_throttler(self):
        self.mock_server.clear_responses()
        self.mock_server.update_response(method="GET",
                                         host=f"{BASE_URL}:{self.port}",
                                         path="/test_per_method",
                                         data=self.mock_server.TEST_RESPONSE,
                                         is_json=False
                                         )
        self.ev_loop.run_until_complete(self.execute_requests(5, self.per_method_rate_throttler))
        pass
