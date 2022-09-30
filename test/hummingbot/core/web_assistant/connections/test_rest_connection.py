import json
import unittest

import aiohttp
from aioresponses import aioresponses

from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection


class RESTConnectionTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    @aioresponses()
    async def test_rest_connection_call(self, mocked_api):
        url = "https://www.test.com/url"
        resp = {"one": 1}
        resp_str = json.dumps(resp)
        mocked_api.get(url, body=json.dumps(resp).encode())

        async with aiohttp.ClientSession() as client_session:
            connection = RESTConnection(client_session)
            request = RESTRequest(method=RESTMethod.GET, url=url)

            ret = await connection.call(request)

        # Tests persistence of the call response after async-with
        self.assertIsInstance(ret, RESTResponse)
        self.assertEqual(url, ret.url)
        self.assertEqual(200, ret.status)
        self.assertEqual("<CIMultiDict('Content-Type': 'application/json')>", str(ret.headers))
        self.assertEqual(resp, ret._json)
        self.assertEqual(resp_str, ret._text)

        j = await ret.json()

        self.assertEqual(resp, j)

        j = await ret.text()

        self.assertEqual(resp_str, j)
