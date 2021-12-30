import asyncio
from threading import Event, Thread
from typing import Optional
import socket
import errno
from urllib.parse import urlparse

import aiohttp
from aiohttp import web


def detect_available_port(starting_port: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        current_port: int = starting_port
        while current_port < 65535:
            try:
                s.bind(("127.0.0.1", current_port))
                break
            except OSError as e:
                if e.errno == errno.EADDRINUSE:
                    current_port += 1
                    continue
        return current_port


class MockWebSocketServerFactory:
    """
    A Class to represent the Humming websockets server factory
    '''
    Attributes
    ----------
    _ws_session : The aiohttp client session.
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
    _ws_session = aiohttp.ClientSession()
    _orig_ws_connect = _ws_session.ws_connect
    _ws_servers = {}
    host = "localhost"
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
        if MockWebSocketServerFactory.url_host_only:
            url = urlparse(url).netloc
        return MockWebSocketServerFactory._ws_servers.get(url)

    @staticmethod
    def start_new_server(url):
        """
        Start the new Humming web server
        :param url: url
        :return: the web server
        """
        port = detect_available_port(8211)
        ws_server = MockWebSocketServer(MockWebSocketServerFactory.host, port)
        if MockWebSocketServerFactory.url_host_only:
            url = urlparse(url).netloc
        MockWebSocketServerFactory._ws_servers[url] = ws_server
        ws_server.start()
        return ws_server

    @staticmethod
    def reroute_ws_connect(client_session_instance, url, **kwargs):
        """
        Reroute to Humming web server if the server has already connected
        :param client_session_instance: The ClientSession instance when calling client.ws_connect(url).
        :param url: url
        :return: the web server
        """
        ws_server = MockWebSocketServerFactory.get_ws_server(url)
        if ws_server is None:
            return MockWebSocketServerFactory._orig_ws_connect(url, **kwargs)
        kwargs.clear()
        return MockWebSocketServerFactory._orig_ws_connect(f"ws://{ws_server.host}:{ws_server.port}", **kwargs)

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
        ws_server = MockWebSocketServerFactory.get_ws_server(url)
        ws_server.wait_til_websocket_is_initialized()
        await ws_server.websocket.send_str(message)

    @staticmethod
    def send_str_threadsafe(url, msg, delay=0):
        """
        Send web socket message in a thead-safe way
        :param url: url
               message: the message to be sent
               delay=0: default is no delay
        """
        ws_server = MockWebSocketServerFactory.get_ws_server(url)
        asyncio.run_coroutine_threadsafe(MockWebSocketServerFactory.send_str(url, msg, delay), ws_server.ev_loop)

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
            ws_server = MockWebSocketServerFactory.get_ws_server(url)
            ws_server.wait_til_websocket_is_initialized()
            await ws_server.websocket.send_json(data)
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
        ws_server = MockWebSocketServerFactory.get_ws_server(url)
        asyncio.run_coroutine_threadsafe(MockWebSocketServerFactory.send_json(url, data, delay), ws_server.ev_loop)


class MockWebSocketServer:
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
        self.websocket: Optional[web.WebSocketResponse] = None
        self._websocket_initialized_event = Event()
        self.stock_responses = {}
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._thread: Optional[Thread] = None

    def add_stock_response(self, request, json_response):
        """
        Stock the json response
        :param request: web socket request
               json response: json response
        """
        self.stock_responses[request] = json_response

    def wait_til_websocket_is_initialized(self):
        self._websocket_initialized_event.wait()

    async def _handler(self, request: web.Request):
        """
        Stock the json response
        """
        self.websocket = web.WebSocketResponse()
        await self.websocket.prepare(request)
        self._websocket_initialized_event.set()
        async for msg in self.websocket:
            stock_responses = [v for k, v in self.stock_responses.items() if k in msg]
            if len(stock_responses) > 0:
                await self.websocket.send_json(stock_responses[0])
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
        self.ev_loop.run_until_complete(self._runner.setup())
        site = web.TCPSite(self._runner, self.host, self.port)
        self.ev_loop.run_until_complete(site.start())
        self._started = True
        self.ev_loop.run_forever()

    async def wait_til_started(self):
        """
         Wait until the Humming web server started
        """
        while not self._started:
            await asyncio.sleep(0.1)

    def start(self):
        """
         Start the Humming Web Server in thread-safe way
        """
        if self.started:
            self.stop()
        self._app = web.Application()
        self._app.router.add_get("/", self._handler)
        self._app.on_shutdown.append(self._on_shutdown)
        self._runner = web.AppRunner(self._app)
        self._thread = Thread(target=self._start, daemon=True)
        self._thread.daemon = True
        self._thread.start()

    async def _on_shutdown(self, _: web.Application):
        await self.websocket.close()

    def stop(self):
        """
         Stop the Humming Web Server in thread-safe way
        """
        self.port = None
        self._started = False
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._runner.shutdown())
        loop.run_until_complete(self._runner.cleanup())
        self.ev_loop.stop()
