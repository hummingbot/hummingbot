import asyncio
import unittest.mock
from threading import Thread
import websockets
from test.integration.humming_web_app import get_open_port
import json
from urllib.parse import urlparse


class HummingWsServerFactory:
    """
    A Class to represent the Humming websockets server factory
    '''
    Attributes
    ----------
    _orig_ws_connect : web servers connection
     _ws_servers : web servers dictionary
    host : host
    url_host_only : if it's url hosted only

    Methods
    -------
    get_ws_server()
    start_new_server(url)
    reroute_ws_connect(url, **kwargs)
    send_str(url, message, delay=0)
    send_str_threadsafe(url, msg, delay=0)
    send_json(url, data, delay=0)
    send_json_threadsafe(url, data, delay=0)
    """
    _orig_ws_connect = websockets.connect
    _ws_servers = {}
    host = "127.0.0.1"
    # url_host_only is used for creating one HummingWSServer to handle all websockets requests and responses for
    # a given url host.
    url_host_only = False

    @staticmethod
    def get_ws_server(url):
        """
        Get the Humming web server
        :param url: url
        :return: the web server
        """
        if HummingWsServerFactory.url_host_only:
            url = urlparse(url).netloc
        return HummingWsServerFactory._ws_servers.get(url)

    @staticmethod
    def start_new_server(url):
        """
        Start the new Humming web server
        :param url: url
        :return: the web server
        """
        port = get_open_port()
        ws_server = HummingWsServer(HummingWsServerFactory.host, port)
        if HummingWsServerFactory.url_host_only:
            url = urlparse(url).netloc
        HummingWsServerFactory._ws_servers[url] = ws_server
        ws_server.start()
        return ws_server

    @staticmethod
    def reroute_ws_connect(url, **kwargs):
        """
        Reroute to Humming web server if the server has already connected
        :param url: url
        :return: the web server
        """
        ws_server = HummingWsServerFactory.get_ws_server(url)
        if ws_server is None:
            return HummingWsServerFactory._orig_ws_connect(url, **kwargs)
        kwargs.clear()
        return HummingWsServerFactory._orig_ws_connect(f"ws://{ws_server.host}:{ws_server.port}", **kwargs)

    @staticmethod
    async def send_str(url, message, delay=0):
        """
        Send web socket message
        :param url: url
               message: the message to be sent
               delay=0: default is no delay
        """
        if delay > 0:
            await asyncio.sleep(delay)
        ws_server = HummingWsServerFactory.get_ws_server(url)
        await ws_server.websocket.send(message)

    @staticmethod
    def send_str_threadsafe(url, msg, delay=0):
        """
        Send web socket message in a thead-safe way
        :param url: url
               message: the message to be sent
               delay=0: default is no delay
        """
        ws_server = HummingWsServerFactory.get_ws_server(url)
        asyncio.run_coroutine_threadsafe(HummingWsServerFactory.send_str(url, msg, delay), ws_server.ev_loop)

    @staticmethod
    async def send_json(url, data, delay=0):
        """
        Send web socket json data
        :param url: url
               data: json data
               delay=0: default is no delay
        """
        try:
            if delay > 0:
                await asyncio.sleep(delay)
            ws_server = HummingWsServerFactory.get_ws_server(url)
            message = json.dumps(data)
            await ws_server.websocket.send(message)
        except Exception as e:
            print(f"HummingWsServerFactory Error: {str(e)}")
            raise e

    @staticmethod
    def send_json_threadsafe(url, data, delay=0):
        """
        Send web socket json data in a thread-safe way
        :param url: url
               data: json data
               delay=0: default is no delay
        """
        ws_server = HummingWsServerFactory.get_ws_server(url)
        asyncio.run_coroutine_threadsafe(HummingWsServerFactory.send_json(url, data, delay), ws_server.ev_loop)


class HummingWsServer:
    """
    A Class to represent the Humming websockets server
    '''
    Attributes
    ----------
    _ev_loop : event loops run asynchronous task
    _started : if started indicator
    host : host
    port : port
    websocket : websocket
    _stock_responses : stocked web response
    host : host

    Methods
    -------
    add_stock_response(self, request, json_response)
    _handler(self, websocket, path)

    """
    def __init__(self, host, port):
        self.ev_loop: None
        self._started: bool = False
        self.host = host
        self.port = port
        self.websocket = None
        self.stock_responses = {}

    def add_stock_response(self, request, json_response):
        """
        Stock the json response
        :param request: web socket request
               json response: json response
        """
        self.stock_responses[request] = json_response

    async def _handler(self, websocket, path):
        """
        Stock the json response
        :param websocket: web socket request
               path: json response
        :return: the web socket
        """
        self.websocket = websocket
        async for msg in self.websocket:
            stock_responses = [v for k, v in self.stock_responses.items() if k in msg]
            if len(stock_responses) > 0:
                await websocket.send(json.dumps(stock_responses[0]))
        print('websocket connection closed')
        return self.websocket

    @property
    def started(self) -> bool:
        """
         Check if started
        :return: the started indicator
        """
        return self._started

    def _start(self):
        """
         Start the Humming Web Server
        """
        self.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ev_loop)
        asyncio.ensure_future(websockets.serve(self._handler, self.host, self.port))
        self.ev_loop.run_forever()

    async def wait_til_started(self):
        """
         Wait until the Humming web server started
        """
        while not self._started:
            await asyncio.sleep(0.1)

    async def _stop(self):
        """
         Stop the event loop
        """
        self.port = None
        self._started = False
        self.ev_loop.stop()

    def start(self):
        """
         Start the Humming Web Server in thread-safe way
        """
        if self.started:
            self.stop()
        thread = Thread(target=self._start)
        thread.daemon = True
        thread.start()

    def stop(self):
        """
         Stop the Humming Web Server in thread-safe way
        """
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
