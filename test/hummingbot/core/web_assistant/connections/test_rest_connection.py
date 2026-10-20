import asyncio
import json
from unittest.mock import AsyncMock
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

import aiohttp
from aioresponses import aioresponses

from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, RESTResponse
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection


class RESTConnectionTest(IsolatedAsyncioWrapperTestCase):
    async def test_call_preserves_default_redirect_behavior(self):
        session = AsyncMock()
        connection = RESTConnection(session)
        request = RESTRequest(method=RESTMethod.GET, url="https://example.invalid")
        await connection.call(request)
        self.assertNotIn("allow_redirects", session.request.call_args.kwargs)

    async def test_call_forwards_explicit_redirect_policy(self):
        session = AsyncMock()
        connection = RESTConnection(session)
        for allow_redirects in (False, True):
            request = RESTRequest(method=RESTMethod.GET, url="https://example.invalid", allow_redirects=allow_redirects)
            await connection.call(request)
            self.assertIs(session.request.call_args.kwargs["allow_redirects"], allow_redirects)

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
