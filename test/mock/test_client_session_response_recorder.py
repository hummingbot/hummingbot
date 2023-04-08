import asyncio
import os
import unittest
from contextlib import asynccontextmanager
from test.mock.client_session_recorder_utils import ClientSessionResponseType
from test.mock.client_session_response_recorder import (
    ClientSessionResponseRecorder,
    ClientSessionResponseRecorderProtocol,
    CustomResponseClassNotClientSessionResponseRecorderError,
)
from unittest.mock import MagicMock, call

from aiohttp import ClientResponse, ClientSession, web
from aiohttp.test_utils import TestServer
from aiohttp.web import Application

os.environ["SQLALCHEMY_WARN_20"] = "1"


class MockClientSessionPlayback:
    id: int = 0

    def __init__(self, id: int, response_type: ClientSessionResponseType):
        self.id = id
        self.response_type = response_type
        self.response_text = None
        self.response_json = None
        self.response_binary = None


RESPONSE_TEXT = "Hello, world!"


class TestClientSessionResponseRecorder(unittest.TestCase):
    @asynccontextmanager
    async def mock_server(self, response_type: str = 'text', content_type: str = 'text/plain'):
        async def handle_text(request):
            return web.Response(text=RESPONSE_TEXT, content_type=content_type or 'text/plain')

        async def handle_json(request):
            return web.json_response({"test": RESPONSE_TEXT}, content_type=content_type or 'application/json')

        app = Application()

        if response_type == 'text':
            app.router.add_route('GET', '/', handle_text)
        else:
            app.router.add_route('GET', '/', handle_json)

        server = TestServer(app)
        await server.start_server()
        yield server
        await server.close()

    async def async_test(self, coro):
        return await coro

    def test_set_parent_recorder(self):
        parent_recorder = MagicMock()
        ClientSessionResponseRecorder.set_parent_recorder(parent_recorder)
        self.assertEqual((parent_recorder), (ClientSessionResponseRecorder._parent_recorder_ref()))

    def test_factory(self):
        class CustomResponse(ClientSessionResponseRecorder):
            custom_attribute = "custom value"

        parent_recorder = MagicMock(spec=ClientSessionResponseRecorderProtocol)

        async def async_test():
            # Test with the default response class
            factory = ClientSessionResponseRecorder.factory(parent_recorder=parent_recorder)
            async with self.mock_server(response_type='text') as server:
                async with ClientSession(response_class=factory) as session:
                    response: ClientSessionResponseRecorder = await session.get(server.make_url('/'))  # type: ignore
                    self.assertIsInstance(response, ClientSessionResponseRecorder)
                    self.assertEqual(response.parent_recorder, parent_recorder)

            # Test with a custom response class
            factory = ClientSessionResponseRecorder.factory(parent_recorder=parent_recorder,
                                                            custom_response_class=CustomResponse)
            async with self.mock_server(response_type='text') as server:
                async with ClientSession(response_class=factory) as session:
                    response: CustomResponse = await session.get(server.make_url('/'))  # type: ignore
                    self.assertIsInstance(response, CustomResponse)
                    self.assertEqual(response.parent_recorder, parent_recorder)
                    self.assertEqual(response.custom_attribute, "custom value")

            # Test with an invalid custom response class
            with self.assertRaises(CustomResponseClassNotClientSessionResponseRecorderError):
                class InvalidCustomResponse(ClientResponse):
                    pass

                _ = ClientSessionResponseRecorder.factory(parent_recorder=parent_recorder,
                                                          custom_response_class=InvalidCustomResponse)

        asyncio.run(async_test())

    def test_database_id(self):
        async def async_test():
            ClientSessionResponseRecorder._database_id = 0
            async with self.mock_server() as server:
                async with ClientSession(response_class=ClientSessionResponseRecorder) as session:
                    recorder: ClientSessionResponseRecorder = await session.get(server.make_url('/'))  # type: ignore
                    self.assertEqual(None, (recorder.database_id))
                    recorder.database_id = 42
                    self.assertEqual((42), (recorder._database_id))
                    self.assertEqual((42), (recorder.database_id))

        asyncio.run(async_test())

    def test_text(self):
        async def async_test():
            ClientSessionResponseRecorder._database_id = 42

            async with self.mock_server(response_type='text') as server:
                # Get the expected response using a regular ClientSession
                async with ClientSession() as session:
                    response: ClientResponse = await session.get(server.make_url('/'))
                    expected_response: str = await response.text(encoding=None, errors='strict')

                # Test the ClientSessionResponseRecorder
                async with ClientSession(response_class=ClientSessionResponseRecorder) as session:
                    response: ClientSessionResponseRecorder = await session.get(server.make_url('/'))  # type: ignore

                    response._update_playback_entry = MagicMock()
                    await response.text()
                    response._update_playback_entry.assert_called_once()
                    response._update_playback_entry.assert_called_once_with(ClientSessionResponseType.WITH_TEXT,
                                                                            response_text=expected_response)

        asyncio.run(async_test())

    def test_json(self):
        async def async_test():
            ClientSessionResponseRecorder._database_id = 42

            async with self.mock_server(response_type='json', content_type='application/json') as server:
                # Get the expected response using a regular ClientSession
                async with ClientSession() as session:
                    response: ClientResponse = await session.get(server.make_url('/'))
                    expected_response = await response.json(encoding=None, content_type="application/json")

                # Test the ClientSessionResponseRecorder
                async with ClientSession(response_class=ClientSessionResponseRecorder) as session:
                    response: ClientSessionResponseRecorder = await session.get(server.make_url('/'))  # type: ignore

                    response._update_playback_entry = MagicMock()
                    await response.json()
                    response._update_playback_entry.assert_called_once()
                    response._update_playback_entry.assert_called_once_with(ClientSessionResponseType.WITH_JSON,
                                                                            response_json=expected_response)

        asyncio.run(async_test())

    def test_read(self):
        async def async_test():
            ClientSessionResponseRecorder._database_id = 42

            async with self.mock_server(response_type='text') as server:
                # Get the expected response using a regular ClientSession
                async with ClientSession() as session:
                    response: ClientResponse = await session.get(server.make_url('/'))
                    expected_response: bytes = await response.read()

                # Test the ClientSessionResponseRecorder
                async with ClientSession(response_class=ClientSessionResponseRecorder) as session:
                    response: ClientSessionResponseRecorder = await session.get(server.make_url('/'))  # type: ignore

                    response._update_playback_entry = MagicMock()
                    await response.read()
                    response._update_playback_entry.assert_called_once()
                    response._update_playback_entry.assert_called_once_with(ClientSessionResponseType.WITH_BINARY,
                                                                            response_binary=expected_response)

        asyncio.run(async_test())

    def test_json_read(self):
        async def async_test():
            ClientSessionResponseRecorder._database_id = 42

            async with self.mock_server(response_type='json', content_type='application/json') as server:
                async with ClientSession(response_class=ClientSessionResponseRecorder) as session:
                    response: ClientSessionResponseRecorder = await session.get(server.make_url('/'))  # type: ignore

                    response._update_playback_entry = MagicMock()
                    await response.json()
                    await response.read()
                    self.assertEqual(2, response._update_playback_entry.call_count)
                    response._update_playback_entry.assert_has_calls(
                        [call(ClientSessionResponseType.WITH_JSON, response_json={'test': 'Hello, world!'}),
                         call(ClientSessionResponseType.WITH_BINARY, response_binary=b'{"test": "Hello, world!"}')])

        asyncio.run(async_test())

    def test_text_read(self):
        async def async_test():
            ClientSessionResponseRecorder._database_id = 42

            async with self.mock_server(response_type='text') as server:
                async with ClientSession(response_class=ClientSessionResponseRecorder) as session:
                    response: ClientSessionResponseRecorder = await session.get(server.make_url('/'))  # type: ignore

                    response._update_playback_entry = MagicMock()
                    await response.text()
                    await response.read()
                    self.assertEqual(2, response._update_playback_entry.call_count)
                    response._update_playback_entry.assert_has_calls(
                        [call(ClientSessionResponseType.WITH_TEXT, response_text='Hello, world!'),
                         call(ClientSessionResponseType.WITH_BINARY, response_binary=b'Hello, world!')])

        asyncio.run(async_test())

    def test__update_playback_entry_text(self):
        parent_recorder: ClientSessionResponseRecorderProtocol = MagicMock()
        parent_recorder.begin.return_value.__enter__.return_value = sql_session = MagicMock()
        ClientSessionResponseRecorder.set_parent_recorder(parent_recorder)

        async def async_test():
            async with self.mock_server(response_type='text') as server:
                async with ClientSession(
                        response_class=ClientSessionResponseRecorder) as session:
                    recorder: ClientSessionResponseRecorder = await session.get(server.make_url('/'))  # type: ignore
                    playback_entry = MockClientSessionPlayback(id=42, response_type=ClientSessionResponseType.WITH_TEXT)
                    sql_session.query.return_value.filter.return_value.one_or_none.return_value = playback_entry

                    # Call the text() method to ensure _update_playback_entry is called within an async context
                    await recorder.text()

                    self.assertEqual(ClientSessionResponseType.WITH_TEXT.name, playback_entry.response_type, )
                    self.assertEqual(RESPONSE_TEXT, playback_entry.response_text, )

        asyncio.run(async_test())

    def test__update_playback_entry_json(self):
        parent_recorder: ClientSessionResponseRecorderProtocol = MagicMock()
        parent_recorder.begin.return_value.__enter__.return_value = sql_session = MagicMock()
        ClientSessionResponseRecorder.set_parent_recorder(parent_recorder)

        async def async_test():
            async with self.mock_server(response_type='json', content_type='application/json') as server:
                async with ClientSession(
                        response_class=ClientSessionResponseRecorder) as session:
                    recorder: ClientSessionResponseRecorder = await session.get(server.make_url('/'))  # type: ignore
                    playback_entry = MockClientSessionPlayback(id=42, response_type=ClientSessionResponseType.WITH_JSON)
                    sql_session.query.return_value.filter.return_value.one_or_none.return_value = playback_entry

                    # Call the json() method to ensure _update_playback_entry is called within an async context
                    await recorder.json(encoding=None, content_type="application/json")

                    self.assertEqual(ClientSessionResponseType.WITH_JSON.name, playback_entry.response_type)
                    self.assertEqual({'test': 'Hello, world!'}, playback_entry.response_json)

        asyncio.run(async_test())

    def test__update_playback_entry_binary(self):
        parent_recorder: ClientSessionResponseRecorderProtocol = MagicMock()
        parent_recorder.begin.return_value.__enter__.return_value = sql_session = MagicMock()
        ClientSessionResponseRecorder.set_parent_recorder(parent_recorder)

        async def async_test():
            async with self.mock_server(response_type='text') as server:
                async with ClientSession(
                        response_class=ClientSessionResponseRecorder) as session:
                    recorder: ClientSessionResponseRecorder = await session.get(server.make_url('/'))  # type: ignore
                    playback_entry = MockClientSessionPlayback(id=42,
                                                               response_type=ClientSessionResponseType.WITH_BINARY)
                    sql_session.query.return_value.filter.return_value.one_or_none.return_value = playback_entry

                    # Call the read() method to ensure _update_playback_entry is called within an async context
                    await recorder.read()

                    self.assertEqual(ClientSessionResponseType.WITH_BINARY.name, playback_entry.response_type, )
                    self.assertEqual(RESPONSE_TEXT.encode(), playback_entry.response_binary, )

        asyncio.run(async_test())

    def test_get_playback_entry(self):
        parent_recorder: ClientSessionResponseRecorderProtocol = MagicMock()
        parent_recorder.begin.return_value.__enter__.return_value = sql_session = MagicMock()
        ClientSessionResponseRecorder.set_parent_recorder(parent_recorder)

        # Create a mock playback_entry
        mock_playback_entry = MockClientSessionPlayback(
            id=42,
            response_type=ClientSessionResponseType.WITH_TEXT
        )

        # Configure the mock SQL session to return the mock_playback_entry
        sql_session.query.return_value.filter.return_value.one_or_none.return_value = mock_playback_entry

        # Initialize a ClientSessionResponseRecorder instance
        async def async_test():
            async with self.mock_server(response_type='json', content_type='application/json') as server:
                async with ClientSession(
                        response_class=ClientSessionResponseRecorder) as session:
                    recorder: ClientSessionResponseRecorder = await session.get(server.make_url('/'))  # type: ignore

                    # Call the get_playback_entry() method
                    playback_entry = recorder.get_playback_entry(sql_session)

                    # Assertions
                    self.assertIsNotNone(playback_entry)
                    self.assertEqual((42), (playback_entry.id))
                    self.assertEqual((ClientSessionResponseType.WITH_TEXT), (playback_entry.response_type))

        asyncio.run(async_test())


if __name__ == "__main__":
    unittest.main()
