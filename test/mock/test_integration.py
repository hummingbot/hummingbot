import asyncio
import os
import tempfile
import unittest
from test.mock.client_session_player import ClientSessionPlayer
from test.mock.client_session_recorder import ClientSessionRecorder
from unittest.mock import MagicMock

from aiohttp import ClientSession, ClientTimeout, web
from aiohttp.test_utils import AioHTTPTestCase, TestServer, unittest_run_loop
from aiohttp.web import Application, json_response


class TestWebIntegration(AioHTTPTestCase):

    async def start_mock_server(self, app):
        server = TestServer(app)
        await server.start_server()
        return server

    async def get_application(self):
        app = Application()
        return app

    @unittest_run_loop
    async def test_record_and_playback(self):
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.close()
        db_path = temp_file.name

        # Define the mock server's response
        async def handle_request():
            return json_response({"message": "Hello, world!"})

        # Create the server application
        app = Application()
        app.router.add_route('GET', '/', handle_request)

        # Start the mock server
        server = await self.start_mock_server(app)
        server_url = server.make_url('/')

        # Record the request/response
        async with ClientSessionRecorder(db_path) as session:
            response = await session.get(server_url)
            await response.json()

        # Simulate the server being unavailable
        await server.close()

        # Playback the recorded request/response and validate the correct behavior of the client
        async with ClientSessionPlayer(db_path) as session:
            response = await session.get(server_url)
            data = await response.json()
            self.assertEqual({"message": "Hello, world!"}, data)

        # Clean up
        await server.close()
        os.remove(temp_file.name)

    @unittest_run_loop
    async def test_successful_request(self):
        async def handle_request():
            return web.Response(text="OK")

        app = Application()
        app.router.add_route('GET', '/', handle_request)

        server = await self.start_mock_server(app)

        async with ClientSession() as session:
            response = await session.get(server.make_url('/'))
            assert response.status == 200
            assert await response.text() == "OK"

    @unittest_run_loop
    async def test_redirect(self):
        async def handle_request(request):
            raise web.HTTPFound(location="/redirected")

        async def redirected_handler(request):
            return web.Response(text="Redirected")

        app = Application()
        app.router.add_route('GET', '/', handle_request)
        app.router.add_route('GET', '/redirected', redirected_handler)
        server = await self.start_mock_server(app)

        async with ClientSession() as session:
            response = await session.get(server.make_url('/'))
            assert response.status == 200
            assert await response.text() == "Redirected"

    @unittest_run_loop
    async def test_timeout(self):
        async def handle_request(request):
            await asyncio.sleep(2)
            return web.Response(text="Timeout")

        app = Application()
        app.router.add_route('GET', '/', handle_request)
        server = await self.start_mock_server(app)

        with self.assertRaises(asyncio.TimeoutError):
            async with ClientSession(timeout=ClientTimeout(total=1)) as session:
                await session.get(server.make_url('/'))

    @unittest_run_loop
    async def test_large_payload(self):
        payload = "a" * (10 * 1024 * 1024)  # 10MB payload

        async def handle_request(request):
            return web.Response(text=payload)

        app = Application()
        app.router.add_route('GET', '/', handle_request)
        server = await self.start_mock_server(app)

        async with ClientSession() as session:
            response = await session.get(server.make_url('/'))
            assert response.status == 200
            assert await response.text() == payload

    @unittest_run_loop
    async def test_error_handling(self):
        async def handle_request(request):
            raise web.HTTPInternalServerError()

        app = Application()
        app.router.add_route('GET', '/', handle_request)
        server = await self.start_mock_server(app)

        async with ClientSession() as session:
            response = await session.get(server.make_url('/'))
            assert response.status == 500

    @unittest_run_loop
    async def test_rate_limit(self):
        rate_limiter = MagicMock(side_effect=[None, None, web.HTTPTooManyRequests()])

        async def handle_request(request):
            rate_limiter()
            return web.Response(text="Not limited")

        app = Application()
        app.router.add_route('GET', '/', handle_request)
        server = await self.start_mock_server(app)

        async with ClientSession() as session:
            response = await session.get(server.make_url('/'))
            assert response.status == 200
            assert await response.text() == "Not limited"

            response = await session.get(server.make_url('/'))
            assert response.status == 200
            assert await response.text() == "Not limited"

            response = await session.get(server.make_url('/'))
            assert response.status == 429


if __name__ == "__main__":
    unittest.main()
