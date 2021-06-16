import asyncio
import threading
import unittest.mock
import websockets
from hummingbot.core.mock_api.mock_web_socket_server import MockWebSocketServerFactory
import json


class MockWebSocketServerFactoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        cls.ws_server = MockWebSocketServerFactory.start_new_server("wss://www.google.com/ws/")
        print(f"1-- {cls.ws_server}\n{cls.ws_server.websocket}")
        cls._patcher = unittest.mock.patch("websockets.connect", autospec=True)
        cls._mock = cls._patcher.start()
        cls._mock.side_effect = MockWebSocketServerFactory.reroute_ws_connect
        # need to wait a bit for the server to be available
        cls.ev_loop.run_until_complete(asyncio.wait_for(cls.ws_server.wait_til_started(), 1))
        print(f"5-- {cls.ws_server}\n{cls.ws_server.websocket}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.ws_server.stop()
        cls._patcher.stop()

    async def _test_web_socket(self):
        uri = "wss://www.google.com/ws/"
        print(f"6-- {self.ws_server}\n{self.ws_server.websocket}")
        # Retry up to 3 times if there is any error connecting to the mock server address and port
        for retry_attempt in range(1, 4):
            try:
                print(f"About to test in thread {threading.current_thread().ident}."
                      f"\n\tServer started? {self.ws_server.started}")
                async with websockets.connect(uri) as websocket:
                    print(f"7-- {self.ws_server}\n{self.ws_server.websocket}")
                    print(f"2-- {websocket}")
                    await MockWebSocketServerFactory.send_str(uri, "aaa")
                    answer = await websocket.recv()
                    print(answer)
                    self.assertEqual("aaa", answer)
                    await MockWebSocketServerFactory.send_json(uri, data={"foo": "bar"})
                    answer = await websocket.recv()
                    print(answer)
                    answer = json.loads(answer)
                    self.assertEqual(answer["foo"], "bar")
                    await self.ws_server.websocket.send("xxx")
                    answer = await websocket.recv()
                    print(answer)
                    self.assertEqual("xxx", answer)
            except OSError:
                # Continue retrying
                continue

            # Stop the retries cycle
            break

    def test_web_socket(self):
        asyncio.get_event_loop().run_until_complete(self._test_web_socket())


if __name__ == '__main__':
    unittest.main()
