import asyncio
import os
import tempfile
import unittest
from test.mock.client_session_player import ClientSessionPlayer
from test.mock.client_session_recorder import ClientSessionRecorder

from aiohttp import web
from aiohttp.test_utils import TestServer
from aiohttp.web import Application, Response, RouteTableDef

os.environ["SQLALCHEMY_WARN_20"] = "1"


class TestClientSessionPlayer(unittest.TestCase):
    @staticmethod
    async def mock_server_handler(request):
        return Response(text="Hello, world!")

    @staticmethod
    async def mock_server_handler_different_response_types(request):
        if request.path == "/test/text":
            response = web.Response(text="Hello, world!")
        elif request.path == "/test/json":
            response = web.json_response({"message": "Hello, world!"})
        elif request.path == "/test/binary":
            response = web.Response(body=b"\x01\x02\x03\x04")
        else:
            response = web.Response(status=404)
        return response

    def setUpTestServer(self, loop, handler):
        app = Application()
        routes = RouteTableDef()

        @routes.get("/test")
        @routes.post("/test")
        @routes.put("/test")
        @routes.delete("/test")
        async def main_handler(request):
            return await handler(request)

        app.router.add_route('*', '/{tail:.*}', handler)

        server = TestServer(app)
        loop.run_until_complete(server.start_server())
        return server

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.server = self.setUpTestServer(self.loop, self.mock_server_handler)
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()

    def tearDown(self):
        self.loop.run_until_complete(self.server.close())
        self.loop.close()
        os.remove(self.temp_file.name)

    def test_no_matching_response(self):
        db_path = self.temp_file.name

        player = ClientSessionPlayer(db_path)

        async def test():
            with self.assertRaises(Exception):
                async with player as client:
                    async with client.get(self.server.make_url("/nonexistent")):
                        pass

        self.loop.run_until_complete(test())

    def test_different_http_methods(self):
        db_path = self.temp_file.name

        # Record responses for different HTTP methods
        recorder = ClientSessionRecorder(db_path)

        async def record():
            async with recorder as client:
                for method in ["POST", "PUT", "DELETE"]:
                    async with client.request(method, str(self.server.make_url("/test"))) as resp:
                        data = await resp.text()
                        self.assertEqual(200, resp.status)
                        self.assertEqual('Hello, world!', data)

        self.loop.run_until_complete(record())

        # Replay the recorded responses
        player = ClientSessionPlayer(db_path)

        async def test():
            async with player as client:
                for method in ["POST", "PUT", "DELETE"]:
                    async with client.request(method, self.server.make_url("/test")) as resp:
                        data = await resp.text()
                        self.assertEqual(200, resp.status, )
                        self.assertEqual("Hello, world!", data, )

        self.loop.run_until_complete(test())

    def test_requests_with_params_and_json(self):
        db_path = self.temp_file.name

        # Record responses for requests with different parameters and JSON payloads
        recorder = ClientSessionRecorder(db_path)

        async def record():
            async with recorder as client:
                async with client.get(self.server.make_url("/test"), params={"key": "value"}) as resp:
                    data = await resp.text()
                    self.assertEqual(200, resp.status)
                    self.assertEqual(data, "Hello, world!")
                async with client.post(self.server.make_url("/test"), json={"key": "value"}) as resp:
                    data = await resp.text()
                    self.assertEqual(200, resp.status)
                    self.assertEqual(data, "Hello, world!")

        self.loop.run_until_complete(record())

        # Replay the recorded responses
        player = ClientSessionPlayer(db_path)

        async def test():
            async with player as client:
                async with client.get(self.server.make_url("/test"), params={"key": "value"}) as resp:
                    data = await resp.text()
                    self.assertEqual(200, resp.status)
                    self.assertEqual(data, "Hello, world!")
                async with client.post(self.server.make_url("/test"), json={"key": "value"}) as resp:
                    data = await resp.text()
                    self.assertEqual(200, resp.status)
                    self.assertEqual(data, "Hello, world!")

        self.loop.run_until_complete(test())

    def test_replay_unrecorded_request(self):
        db_path = self.temp_file.name

        player = ClientSessionPlayer(db_path)

        async def test():
            async with player as client:
                with self.assertRaises(Exception) as context:
                    async with client.get(self.server.make_url("/unrecorded")):
                        pass
                self.assertIn("No matching response found", str(context.exception))

        self.loop.run_until_complete(test())

    def test_replay_multiple_recorded_responses(self):
        db_path = self.temp_file.name

        # Record the response twice
        recorder = ClientSessionRecorder(db_path)

        async def record():
            for _ in range(2):
                async with recorder as client:
                    async with client.get(self.server.make_url("/test")) as resp:
                        data = await resp.text()
                        self.assertEqual(200, resp.status)
                        self.assertEqual(data, "Hello, world!")

        self.loop.run_until_complete(record())

        # Replay the recorded responses
        player = ClientSessionPlayer(db_path)

        async def test():
            async with player as client:
                async with client.get(self.server.make_url("/test")) as resp:
                    data = await resp.text()
                    self.assertEqual(200, resp.status)
                    self.assertEqual(data, "Hello, world!")

                async with client.get(self.server.make_url("/test")) as resp:
                    data = await resp.text()
                    self.assertEqual(200, resp.status)
                    self.assertEqual(data, "Hello, world!")

        self.loop.run_until_complete(test())

    def test_different_response_types(self):
        db_path = self.temp_file.name

        # Set up a new test server with the different response types handler
        async def server_reset():
            await self.server.close()
        self.loop.run_until_complete(server_reset())

        self.server = self.setUpTestServer(self.loop, self.mock_server_handler_different_response_types)

        # Record responses with different content types
        recorder = ClientSessionRecorder(db_path)

        async def record():
            async with recorder as client:
                # Text response
                async with client.get(self.server.make_url("/test/text")) as resp:
                    data = await resp.text()
                    self.assertEqual(200, resp.status)
                    self.assertEqual(data, "Hello, world!")

                # JSON response
                async with client.get(self.server.make_url("/test/json")) as resp:
                    data = await resp.json()
                    self.assertEqual(200, resp.status)
                    self.assertEqual(data, {"message": "Hello, world!"})

                # Binary response
                async with client.get(self.server.make_url("/test/binary")) as resp:
                    data = await resp.read()
                    self.assertEqual(200, resp.status)
                    self.assertEqual(data, b"\x01\x02\x03\x04")

        self.loop.run_until_complete(record())

        # Replay the recorded responses
        player = ClientSessionPlayer(db_path)

        async def test():
            async with player as client:
                # Text response
                async with client.get(self.server.make_url("/test/text")) as resp:
                    data = await resp.text()
                    self.assertEqual(200, resp.status)
                    self.assertEqual(data, "Hello, world!")

                # JSON response
                async with client.get(self.server.make_url("/test/json")) as resp:
                    data = await resp.json()
                    self.assertEqual(200, resp.status)
                    self.assertEqual(data, {"message": "Hello, world!"})

                # Binary response
                async with client.get(self.server.make_url("/test/binary")) as resp:
                    data = await resp.read()
                    self.assertEqual(200, resp.status)
                    self.assertEqual(data, b"\x01\x02\x03\x04")

        self.loop.run_until_complete(test())

    def test_client_session_player(self):
        db_path = self.temp_file.name

        # Record the response
        recorder = ClientSessionRecorder(db_path)

        async def record():
            async with recorder as client:
                async with client.get(self.server.make_url("/test")) as resp:
                    data = await resp.text()
                    self.assertEqual(200, resp.status, )
                    self.assertEqual("Hello, world!", data, )

        self.loop.run_until_complete(record())

        # Replay the recorded response
        player = ClientSessionPlayer(db_path)

        async def test():
            async with player as client:
                async with client.get(self.server.make_url("/test")) as resp:
                    data = await resp.text()
                    self.assertEqual(200, resp.status, )
                    self.assertEqual("Hello, world!", data, )

        self.loop.run_until_complete(test())

        # Test if the player is using the recorded response and not making a new request
        original_handler = self.mock_server_handler

        async def should_not_be_called(request):
            raise Exception("This should not be called")

        self.mock_server_handler = should_not_be_called

        self.loop.run_until_complete(test())

        self.mock_server_handler = original_handler


if __name__ == "__main__":
    unittest.main()
