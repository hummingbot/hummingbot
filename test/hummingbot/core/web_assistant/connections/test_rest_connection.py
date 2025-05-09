import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

import aiohttp
from aioresponses import aioresponses

from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection


class RESTConnectionTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    @aioresponses()
    async def test_rest_connection_call(self, mocked_api):
        url = "https://www.test.com/url"
        resp = {"one": 1}
        mocked_api.get(url, body=json.dumps(resp).encode())

        client_session = aiohttp.ClientSession()
        connection = RESTConnection(client_session)
        request = RESTRequest(method=RESTMethod.GET, url=url)

        ret = await (connection.call(request))

        self.assertIsInstance(ret, RESTResponse)
        self.assertEqual(url, ret.url)
        self.assertEqual(200, ret.status)

        j = await (ret.json())

        self.assertEqual(resp, j)
        await (client_session.close())
