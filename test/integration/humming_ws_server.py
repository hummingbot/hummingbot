import asyncio
import unittest.mock
from threading import Thread
import websockets
from test.integration.humming_web_app import get_open_port
import json
from urllib.parse import urlparse


class HummingWsServerFactory:
    _orig_ws_connect = websockets.connect
    _ws_servers = {}
    host = "127.0.0.1"
    # url_host_only is used for creating one HummingWSServer to handle all websockets requests and responses for
    # a given url host.
    url_host_only = False

    @staticmethod
    def get_ws_server(url):
        if HummingWsServerFactory.url_host_only:
            url = urlparse(url).netloc
        return HummingWsServerFactory._ws_servers.get(url)

    @staticmethod
    def start_new_server(url):
        port = get_open_port()
        ws_server = HummingWsServer(HummingWsServerFactory.host, port)
        if HummingWsServerFactory.url_host_only:
            url = urlparse(url).netloc
        HummingWsServerFactory._ws_servers[url] = ws_server
        ws_server.start()
        return ws_server

    @staticmethod
    def reroute_ws_connect(url, **kwargs):
        ws_server = HummingWsServerFactory.get_ws_server(url)
        if ws_server is None:
            return HummingWsServerFactory._orig_ws_connect(url, **kwargs)
        kwargs.clear()
        return HummingWsServerFactory._orig_ws_connect(f"ws://{ws_server.host}:{ws_server.port}", **kwargs)

    @staticmethod
    async def send_str(url, message, delay=0):
        if delay > 0:
            await asyncio.sleep(delay)
        ws_server = HummingWsServerFactory.get_ws_server(url)
        await ws_server.websocket.send(message)

    @staticmethod
    def send_str_threadsafe(url, msg, delay=0):
        ws_server = HummingWsServerFactory.get_ws_server(url)
        asyncio.run_coroutine_threadsafe(HummingWsServerFactory.send_str(url, msg, delay), ws_server.ev_loop)

    @staticmethod
    async def send_json(url, data, delay=0):
        if delay > 0:
            await asyncio.sleep(delay)
        ws_server = HummingWsServerFactory.get_ws_server(url)
        await ws_server.websocket.send(json.dumps(data))

    @staticmethod
    def send_json_threadsafe(url, data, delay=0):
        ws_server = HummingWsServerFactory.get_ws_server(url)
        asyncio.run_coroutine_threadsafe(HummingWsServerFactory.send_json(url, data, delay), ws_server.ev_loop)


class HummingWsServer:

    def __init__(self, host, port):
        self.ev_loop: None
        self._started: bool = False
        self.host = host
        self.port = port
        self.websocket = None
        self.stock_responses = {}

    def add_stock_response(self, request, json_response):
        self.stock_responses[request] = json_response

    async def _handler(self, websocket, path):
        self.websocket = websocket
        async for msg in self.websocket:
            stock_responses = [v for k, v in self.stock_responses.items() if k in msg]
            if len(stock_responses) > 0:
                await websocket.send(json.dumps(stock_responses[0]))
        print('websocket connection closed')
        return self.websocket

    @property
    def started(self) -> bool:
        return self._started

    def _start(self):
        self.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ev_loop)
        asyncio.ensure_future(websockets.serve(self._handler, self.host, self.port))
        self.ev_loop.run_forever()

    async def wait_til_started(self):
        while not self._started:
            await asyncio.sleep(0.1)

    async def _stop(self):
        self.port = None
        self._started = False
        self.ev_loop.stop()

    def start(self):
        if self.started:
            self.stop()
        thread = Thread(target=self._start)
        thread.daemon = True
        thread.start()

    def stop(self):
        asyncio.run_coroutine_threadsafe(self._stop(), self.ev_loop)


class HummingWsServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        cls.ws_server = HummingWsServerFactory.start_new_server("ws://www.google.com/ws/")
        cls._patcher = unittest.mock.patch("websockets.connect", autospec=True)
        cls._mock = cls._patcher.start()
        cls._mock.side_effect = HummingWsServerFactory.reroute_ws_connect

    @classmethod
    def tearDownClass(cls) -> None:
        cls._patcher.stop()

    async def _test_web_socket(self):
        uri = "ws://www.google.com/ws/"
        async with websockets.connect(uri) as websocket:
            await HummingWsServerFactory.send_str(uri, "aaa")
            answer = await websocket.recv()
            print(answer)
            self.assertEqual("aaa", answer)
            await HummingWsServerFactory.send_json(uri, data={"foo": "bar"})
            answer = await websocket.recv()
            print(answer)
            answer = json.loads(answer)
            self.assertEqual(answer["foo"], "bar")
            await self.ws_server.websocket.send("xxx")
            answer = await websocket.recv()
            print(answer)
            self.assertEqual("xxx", answer)

    def test_web_socket(self):
        asyncio.get_event_loop().run_until_complete(self._test_web_socket())


if __name__ == '__main__':
    unittest.main()
