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

    async def test_request_is_sent_again_when_the_pooled_connection_was_closing(self):
        # aiohttp raises ClientConnectionResetError("Cannot write to closing transport") when the
        # server closed a keep-alive connection after the pool handed it out; the request never
        # left the client (hummingbot/hummingbot#7628, #7629), so one retry on a live connection is safe
        url = "https://www.test.com/url"
        error_type = getattr(aiohttp, "ClientConnectionResetError", aiohttp.ClientOSError)
        good_response = object()
        attempts = []

        async def fake_request(**kwargs):
            attempts.append(kwargs)
            if len(attempts) == 1:
                raise error_type("Cannot write to closing transport")
            return good_response

        client_session = aiohttp.ClientSession()
        client_session.request = fake_request
        connection = RESTConnection(client_session)
        request = RESTRequest(method=RESTMethod.POST, url=url, data="payload")

        ret = await connection.call(request)

        self.assertEqual(2, len(attempts))
        self.assertEqual(attempts[0], attempts[1])
        self.assertIs(good_response, ret._aiohttp_response)
        await client_session.close()

    async def test_other_connection_errors_are_not_retried(self):
        url = "https://www.test.com/url"
        attempts = []

        async def fake_request(**kwargs):
            attempts.append(kwargs)
            raise aiohttp.ClientOSError("Connection reset by peer")

        client_session = aiohttp.ClientSession()
        client_session.request = fake_request
        connection = RESTConnection(client_session)

        with self.assertRaises(aiohttp.ClientOSError):
            await connection.call(RESTRequest(method=RESTMethod.POST, url=url, data="payload"))

        self.assertEqual(1, len(attempts))
        await client_session.close()

    async def test_a_second_closing_transport_is_raised(self):
        url = "https://www.test.com/url"
        error_type = getattr(aiohttp, "ClientConnectionResetError", aiohttp.ClientOSError)
        attempts = []

        async def fake_request(**kwargs):
            attempts.append(kwargs)
            raise error_type("Cannot write to closing transport")

        client_session = aiohttp.ClientSession()
        client_session.request = fake_request
        connection = RESTConnection(client_session)

        with self.assertRaises(error_type):
            await connection.call(RESTRequest(method=RESTMethod.GET, url=url))

        self.assertEqual(2, len(attempts))
        await client_session.close()

    async def test_a_streaming_body_is_not_sent_again(self):
        # a file or async iterable may already be partly consumed; only buffered bodies are retried
        url = "https://www.test.com/url"
        error_type = getattr(aiohttp, "ClientConnectionResetError", aiohttp.ClientOSError)
        attempts = []

        async def fake_request(**kwargs):
            attempts.append(kwargs)
            raise error_type("Cannot write to closing transport")

        async def body_chunks():
            yield b"payload"

        client_session = aiohttp.ClientSession()
        client_session.request = fake_request
        connection = RESTConnection(client_session)

        with self.assertRaises(error_type):
            await connection.call(RESTRequest(method=RESTMethod.POST, url=url, data=body_chunks()))

        self.assertEqual(1, len(attempts))
        await client_session.close()
