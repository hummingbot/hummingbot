import asyncio
import json
import unittest.mock

import aiohttp

from hummingbot.core.mock_api.mock_web_socket_server import MockWebSocketServerFactory


class MockWebSocketServerFactoryTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ws_server = MockWebSocketServerFactory.start_new_server("wss://www.google.com/ws/")

    async def asyncSetUp(self) -> None:
        self.session = aiohttp.ClientSession()
        MockWebSocketServerFactory._orig_ws_connect = self.session.ws_connect

        self._patcher = unittest.mock.patch("aiohttp.client.ClientSession.ws_connect", autospec=True)
        self._mock = self._patcher.start()
        self._mock.side_effect = MockWebSocketServerFactory.reroute_ws_connect

        # need to wait a bit for the server to be available
        await asyncio.wait_for(MockWebSocketServerFactoryTest.ws_server.wait_til_started(), 1)

    async def asyncTearDown(self) -> None:
        self._patcher.stop()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.ws_server.stop()

    async def test_web_socket(self):
        uri = "wss://www.google.com/ws/"

        # Retry up to 3 times if there is any error connecting to the mock server address and port
        for retry_attempt in range(3):
            try:
                async with self.session.ws_connect(uri) as websocket:
                    await MockWebSocketServerFactory.send_str(uri, "aaa")
                    answer = await websocket.receive_str()
                    self.assertEqual("aaa", answer)

                    await MockWebSocketServerFactory.send_json(uri, data={"foo": "bar"})
                    answer = await websocket.receive_str()
                    answer = json.loads(answer)
                    self.assertEqual(answer["foo"], "bar")

                    await self.ws_server.websocket.send_str("xxx")
                    answer = await websocket.receive_str()
                    self.assertEqual("xxx", answer)
            except OSError:
                if retry_attempt == 2:
                    raise
                # Continue retrying
                continue

            # Stop the retries cycle
            break


if __name__ == '__main__':
    unittest.main()
