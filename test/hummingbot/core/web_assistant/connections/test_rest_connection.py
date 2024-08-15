import asyncio
import json
import unittest
from typing import Awaitable

import aiohttp
from aioresponses import aioresponses

from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection


class RESTConnectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_rest_connection_call(self, mocked_api):
        url = "https://www.test.com/url"
        resp = {"one": 1}
        mocked_api.get(url, body=json.dumps(resp).encode())

        client_session = aiohttp.ClientSession(loop=self.ev_loop)
        connection = RESTConnection(client_session)
        request = RESTRequest(method=RESTMethod.GET, url=url)

        ret = self.async_run_with_timeout(connection.call(request))

        self.assertIsInstance(ret, RESTResponse)
        self.assertEqual(url, ret.url)
        self.assertEqual(200, ret.status)

        j = self.async_run_with_timeout(ret.json())

        self.assertEqual(resp, j)
