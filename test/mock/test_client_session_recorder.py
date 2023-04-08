import asyncio
import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from test.mock.client_session_recorder import ClientSessionRecorder
from test.mock.client_session_recorder_utils import ClientSessionResponseType
from test.mock.client_session_response_recorder import ClientSessionResponseRecorder
from test.mock.client_session_wrapped_request import ClientSessionWrappedRequest
from typing import List, Optional
from unittest import mock

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

TEST_URL = "/test_endpoint"
POST_URL = "/test_post_endpoint"
PUT_URL = "/test_put_endpoint"
DELETE_URL = "/test_delete_endpoint"
JSON_DATA = {"key": "value"}
QUERY_PARAMS = {"param1": "value1", "param2": "value2"}
CUSTOM_HEADER = {"Custom-Header": "CustomValue"}

RESPONSE_TEXT = "Hello, world!"
RESPONSE_JSON = {"message": "Hello, world!"}

os.environ["SQLALCHEMY_WARN_20"] = "1"


async def handle_error(request):
    return web.Response(status=500)


class TestClientSessionRecorder(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.recorder = ClientSessionRecorder(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    @asynccontextmanager
    async def mock_server_and_client(self, response_type: str = 'text', content_type: str = 'text/plain',
                                     extra_routes: Optional[List] = None):
        async def handle_text(request):
            return web.Response(text=RESPONSE_TEXT, content_type=content_type or 'text/plain')

        async def handle_json(request):
            return web.json_response(RESPONSE_JSON, content_type=content_type or 'application/json')

        if extra_routes is None:
            extra_routes: List = []

        app = web.Application()

        if response_type == 'text':
            app.router.add_route('GET', '/', handle_text)
            app.router.add_route('POST', '/', handle_text)
            app.router.add_route('PUT', '/', handle_text)
            app.router.add_route('DELETE', '/', handle_text)
        else:
            app.router.add_route('GET', '/', handle_json)
            app.router.add_route('POST', '/', handle_json)
            app.router.add_route('PUT', '/', handle_json)
            app.router.add_route('DELETE', '/', handle_json)

        for route in extra_routes:
            app.router.add_route(route.method, route.path, route.handler)

        async with TestServer(app) as server, TestClient(server) as client:
            await server.start_server()
            yield server, client

    def test_record_text_response(self):
        async def _test():
            async with self.mock_server_and_client(response_type='text') as (server, _):
                async with self.recorder as client_recorder:
                    async with client_recorder.get(server.make_url('/')) as resp:
                        self.assertEqual(await resp.text(), RESPONSE_TEXT)

            records = self.recorder.get_records()
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(record['response_code'], 200)
            self.assertEqual(record['response_type'], ClientSessionResponseType.WITH_TEXT)

        asyncio.run(_test())

    def test_record_text_response_with_context(self):
        async def _test():
            async with self.mock_server_and_client(response_type='text') as (server, _):
                async with ClientSessionRecorder(':memory:') as client_recorder:
                    self.assertIsInstance(client_recorder, ClientSessionWrappedRequest)
                    async with client_recorder.get(server.make_url('/')) as resp:
                        self.assertIsInstance(resp, ClientSessionResponseRecorder)
                        self.assertEqual(await resp.text(), RESPONSE_TEXT)
                    # No handle to inspect the records since the client_recorder is not a ClientSessionRecorder
                    # TODO: Add a way to get the records by returning ClientSessionRecorder as an enhanced ClientSessionWrappedRequest
                    # records = self.recorder.get_records()
                    # self.assertEqual(len(records), 1)
                    # record = records[0]
                    # self.assertEqual(record['response_code'], 200)
                    # self.assertEqual(record['response_type'], ClientSessionResponseType.WITH_TEXT)

        asyncio.run(_test())

    def test_record_json_response(self):
        async def _test():
            async with self.mock_server_and_client(response_type='json', content_type='application/json') as (
                    server, _):
                async with self.recorder as client_recorder:
                    async with client_recorder.get(server.make_url('/')) as resp:
                        self.assertEqual(RESPONSE_JSON, await resp.json(), )

            records = self.recorder.get_records()
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(200, record['response_code'], )
            self.assertEqual(ClientSessionResponseType.WITH_JSON, record['response_type'], )

        asyncio.run(_test())

    def test_request_with_params(self):
        async def _test():
            async with self.mock_server_and_client(response_type='text') as (server, _):
                params = {'key': 'value'}
                async with self.recorder as client_recorder:
                    async with client_recorder.get(server.make_url('/'), params=params) as resp:
                        self.assertEqual(RESPONSE_TEXT, await resp.text())

            records = self.recorder.get_records()
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(record['request_params'], params)

        asyncio.run(_test())

    def test_request_with_json(self):
        async def _test():
            async with self.mock_server_and_client(response_type='text') as (server, _):
                json_data = {'key': 'value'}
                async with self.recorder as client_recorder:
                    async with client_recorder.post(server.make_url('/'), json=json_data) as resp:
                        self.assertEqual(RESPONSE_TEXT, await resp.text())

            records = self.recorder.get_records()
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(record['request_json'], json_data)

        asyncio.run(_test())

    def test_record_multiple_responses(self):
        async def _test():
            async with self.mock_server_and_client(response_type='text') as (server, _):
                async with self.recorder as client_recorder:
                    async with client_recorder.get(server.make_url('/')) as resp:
                        self.assertEqual(RESPONSE_TEXT, await resp.text(), )

                    async with client_recorder.get(server.make_url('/')) as resp:
                        self.assertEqual(RESPONSE_TEXT, await resp.text(), )

            records = self.recorder.get_records()
            self.assertEqual(len(records), 2)
            for record in records:
                self.assertEqual(200, record['response_code'], )
                self.assertEqual(ClientSessionResponseType.WITH_TEXT, record['response_type'], )

        asyncio.run(_test())

    def test_concurrent_requests(self):
        async def _test():
            async with self.mock_server_and_client(response_type='text') as (server, _):
                async with self.recorder as client_recorder:
                    tasks = [client_recorder.get(server.make_url('/')) for _ in range(5)]
                    await asyncio.gather(*tasks)

            records = self.recorder.get_records()
            self.assertEqual(5, len(records))
            for record in records:
                self.assertEqual(200, record['response_code'])
                self.assertEqual(ClientSessionResponseType.HEADER_ONLY, record['response_type'])

        asyncio.run(_test())

    def test_error_response(self):
        async def _test():
            extra_routes = [web.RouteDef("GET", "/error", handle_error, {})]
            async with self.mock_server_and_client(extra_routes=extra_routes) as (server, _):
                async with self.recorder as client_recorder:
                    async with client_recorder.get(server.make_url('/error')) as resp:
                        self.assertEqual(500, resp.status)

            records = self.recorder.get_records()
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(500, record['response_code'])
            self.assertEqual(ClientSessionResponseType.HEADER_ONLY, record['response_type'])

        asyncio.run(_test())

    def test_post_put_delete_requests(self):
        async def _test():
            async with self.mock_server_and_client(response_type='text') as (server, _):
                async with self.recorder as client_recorder:
                    methods = ['POST', 'PUT', 'DELETE']
                    for method in methods:
                        async with client_recorder.request(method, server.make_url('/')) as resp:
                            self.assertEqual(RESPONSE_TEXT, await resp.text())

            records = self.recorder.get_records()
            self.assertEqual(len(records), 3)
            for record in records:
                self.assertEqual(200, record['response_code'])
                self.assertEqual(ClientSessionResponseType.WITH_TEXT, record['response_type'])

        asyncio.run(_test())

    def test_custom_headers(self):
        async def _test():
            headers = {'Custom-Header': 'Test'}
            async with self.mock_server_and_client(response_type='text') as (server, _):
                async with self.recorder as client_recorder:
                    async with client_recorder.get(server.make_url('/'), headers=headers) as resp:
                        self.assertEqual(RESPONSE_TEXT, await resp.text())

            records = self.recorder.get_records()
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(200, record['response_code'])
            self.assertEqual(ClientSessionResponseType.WITH_TEXT, record['response_type'])
            self.assertEqual(headers, record['request_headers'])

        asyncio.run(_test())

    def test_request_exception(self):
        async def _test():
            async with self.mock_server_and_client(response_type='text') as (server, _):
                async with self.recorder as client_recorder:
                    # Simulate an exception during the request, mocking request does not work.
                    with mock.patch.object(aiohttp.ClientSession, 'get', side_effect=Exception("Test exception")):
                        with self.assertRaises(Exception) as cm:
                            async with client_recorder.get(server.make_url('/')):
                                pass
                        self.assertEqual(str(cm.exception), "Test exception")

            records = self.recorder.get_records()
            self.assertEqual(len(records), 0)  # Ensure the request was not recorded

        asyncio.run(_test())

    def test_custom_response_class(self):
        async def _test():
            class CustomResponse(ClientSessionResponseRecorder):
                async def custom_method(self):
                    return await self.text()

            async with self.mock_server_and_client(response_type='text') as (server, _):
                async with self.recorder(response_class=CustomResponse) as client_recorder:
                    async with client_recorder.get(server.make_url('/')) as resp:
                        self.assertEqual(RESPONSE_TEXT, await resp.custom_method())

            records = self.recorder.get_records()
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(200, record['response_code'])
            self.assertEqual(ClientSessionResponseType.WITH_TEXT, record['response_type'])

        asyncio.run(_test())

    def test_call_method(self):
        async def _test():
            class CustomResponse(ClientSessionResponseRecorder):
                async def custom_method(self):
                    return await self.text()

            async with self.mock_server_and_client(response_type='text') as (server, _):
                async with self.recorder() as client_recorder:
                    async with client_recorder.get(server.make_url('/')) as resp:
                        self.assertEqual(RESPONSE_TEXT, await resp.text())

                async with self.recorder(response_class=CustomResponse) as client_recorder:
                    async with client_recorder.get(server.make_url('/')) as resp:
                        self.assertEqual(RESPONSE_TEXT, await resp.custom_method())

            records = self.recorder.get_records()
            self.assertEqual(len(records), 2)
            record1, record2 = records
            self.assertEqual(200, record1['response_code'])
            self.assertEqual(ClientSessionResponseType.WITH_TEXT, record1['response_type'])
            self.assertEqual(200, record2['response_code'])
            self.assertEqual(ClientSessionResponseType.WITH_TEXT, record2['response_type'])

        asyncio.run(_test())

    def test_call_method_with_request_wrapper(self):
        async def custom_request_wrapper(*args, **kwargs):
            class CustomResponse(ClientSessionResponseRecorder):
                custom_attribute = "Custom Value"

                async def custom_method(self):
                    return await self.text()

            async with aiohttp.ClientSession(response_class=CustomResponse) as session:
                kwargs.pop("wrapped_session", None)
                response = await session._request(*args, **kwargs)
                return response

        async def _test():
            async with self.mock_server_and_client(response_type='text') as (server, _):
                async with self.recorder() as client_recorder:
                    async with client_recorder.get(server.make_url('/')) as resp:
                        self.assertEqual(RESPONSE_TEXT, await resp.text())
                        self.assertFalse(hasattr(resp, "custom_attribute"))

                records = self.recorder.get_records()
                self.assertEqual(len(records), 1)
                self.assertEqual(200, records[0]['response_code'])
                self.assertEqual(ClientSessionResponseType.WITH_TEXT, records[0]['response_type'])

                async with self.recorder(request_wrapper=custom_request_wrapper) as client_recorder:
                    async with client_recorder.get(server.make_url('/')) as resp:
                        self.assertEqual(RESPONSE_TEXT, await resp.text())
                        self.assertTrue(hasattr(resp, "custom_attribute"))
                        self.assertEqual("Custom Value", resp.custom_attribute)

                # Custom wrapper is not generating records
                records = self.recorder.get_records()
                self.assertEqual(len(records), 1)
                self.assertEqual(200, records[0]['response_code'])
                self.assertEqual(ClientSessionResponseType.WITH_TEXT, records[0]['response_type'])

        asyncio.run(_test())
