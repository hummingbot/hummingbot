#!/usr/bin/env python

import asyncio
from aiohttp import web
import logging
import random
from typing import Optional
from yarl import URL
from collections import namedtuple
import requests
from threading import Thread

StockResponse = namedtuple("StockResponse", "method host path params is_json response")


def get_open_port() -> int:
    """
    Get the open port number
    :return: Get the opened port number
    """
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


class MockWebServer:
    """
    A Class to represent the Humming Web App
    '''
    Attributes
    ----------
    __instance : Humming Web App instance
    _ev_loop : event loops run asynchronous task
    _impl : web applicaiton
    _runner : web runner
    _started : if started indicator
    _stock_responses : stocked web response
    host : host

    Methods
    -------
    get_instance()
    _handler(self, request: web.Request)
    send_ws_msg(self, ws_path, message)
    send_ws_json(self, ws_path, data)
    update_response(self, method, host, path, data, params=None, is_json=True)
    add_host_to_mock(self, host, ignored_paths=[])
    reroute_local(url)
    reroute_request(self, method, url, **kwargs)
    """
    TEST_RESPONSE = f"hello {str(random.randint(0, 10000000))}"
    _hosts_to_mock = {}
    host = "127.0.0.1"
    _port: Optional[int] = None

    @classmethod
    def get_instance(cls):
        """
        Initiate a Humming Web App instance
        :return: An instance of Humming Web App
        """
        instance = cls.__dict__.get("__instance__")
        if instance is None:
            cls.__instance__ = instance = cls()
        return instance

    def __init__(self):
        """
        Constructs all the necessary attributes for the Humming Web object
        """
        self._ev_loop: asyncio.AbstractEventLoop = None
        self._impl: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._started: bool = False
        self._stock_responses = []
        self.host = "127.0.0.1"

    async def _handler(self, request: web.Request):
        """
        Handle the passed in the web request, and return the response based on request query or post
        :param request: web request
        :return: response in json format, or string, or response itself
        """
        # Add a little sleep to simulate real API requests and also to make sure events are triggers before wait_for
        # await asyncio.sleep(0.01)
        method, req_path = request.method, request.path
        req_path = req_path[1:]
        host = req_path[0:req_path.find("/")]
        path = req_path[req_path.find("/"):]
        resps = [x for x in self._stock_responses if x.method == method and x.host == host and x.path == path]
        if len(resps) > 1:
            params = dict(request.query)
            params.update(dict(await request.post()))
            resps = [x for x in resps if x.params is not None and all(k in params and str(v) == params[k]
                                                                      for k, v in x.params.items())]
        if not resps:
            raise web.HTTPNotFound(text=f"No Match found for {host}{path} {method}")
        is_json, response = resps[0].is_json, resps[0].response
        if is_json:
            return web.json_response(data=response)
        elif type(response) == str:
            return web.Response(text=response)
        else:
            return response

    async def send_ws_msg(self, ws_path, message):
        """
        Send out the web socket message
        :param ws_path: web socket path
               message: the web socket message to be sent out
        """
        ws = [ws for path, ws in self._ws_response.items() if ws_path in path][0]
        await ws.send_str(message)

    async def send_ws_json(self, ws_path, data):
        """
        Send out json data by web socket
        :param ws_path: web socket path
               message: the json data to be sent out
        """
        ws = [ws for path, ws in self._ws_response.items() if ws_path in path][0]
        await ws.send_json(data=data)

    def clear_responses(self):
        self._stock_responses.clear()

    # To add or update data which will later be responded to a request according to its method, host and path
    def update_response(self, method, host, path, data, params=None, is_json=True):
        """
        Add or update data which will later be responded to a request according to its method, host and path
        :param method: request method
               host: request host
               path: request path
               data: data to respond
               params=None: request parameters
               is_json=True: if it's in Json format
        """
        method = method.upper()
        resp_data = [x for x in self._stock_responses if x.method == method and x.host == host and x.path == path
                     and x.params == params]
        if resp_data:
            self._stock_responses.remove(resp_data[0])
        self._stock_responses.append(StockResponse(method, host, path, params, is_json, data))

    def add_host_to_mock(self, host, ignored_paths=[]):
        """
        Add the request host to the mock
        :param host: request host
               ignored_paths=[]: the paths for the mock
        """
        MockWebServer._hosts_to_mock[host] = ignored_paths

    # reroute a url if it is one of the hosts we handle.
    @staticmethod
    def reroute_local(url):
        """
         reroute a url if it is one of the hosts we handle
        :param url: the original url
        :return: the rerouted url
        """
        a_url = URL(url)

        if a_url.host in MockWebServer._hosts_to_mock and not any(x in a_url.path for x in
                                                                  MockWebServer._hosts_to_mock[a_url.host]):
            host_path = f"/{a_url.host}{a_url.path}"
            query = a_url.query
            a_url = a_url.with_scheme("http").with_host(MockWebServer.host).with_port(MockWebServer._port)\
                .with_path(host_path).with_query(query)
        return a_url

    orig_session_request = requests.Session.request

    # self here is not an instance of HummingWebApp, it is for mocking Session.request
    @staticmethod
    def reroute_request(self, method, url, **kwargs):
        """
         reroute the request from the rerouted url
        :param method: request method
               url: the rerouted url
        :return: the rerouted request
        """
        a_url = MockWebServer.reroute_local(url)
        return MockWebServer.orig_session_request(self, method, str(a_url), **kwargs)

    @property
    def started(self) -> bool:
        """
         Check if started
        :return: the started indicator
        """
        return self._started

    @property
    def port(self) -> Optional[int]:
        """
         Get the port
        :return: the port
        """
        return type(self)._port

    async def _start(self):
        """
         Start the Humming Wep App instance
        """
        try:
            MockWebServer._port = get_open_port()
            self._impl: Optional[web.Application] = web.Application()
            self._impl.add_routes([web.route("*", '/{tail:.*}', self._handler)])
            self._runner = web.AppRunner(self._impl)
            await self._runner.setup()
            site = web.TCPSite(self._runner, host=MockWebServer.host, port=MockWebServer._port)
            await site.start()
            self._started = True
        except Exception:
            logging.error("oops!", exc_info=True)

    def _wait_til_started(self):
        """
        Check if the instance started
        :return: if the instance started
        """
        future = asyncio.run_coroutine_threadsafe(self.wait_til_started(), self._ev_loop)
        return future.result()

    async def wait_til_started(self):
        """
         Wait until the instance started
        """
        while not self._started:
            await asyncio.sleep(0.1)

    async def _stop(self):
        """
         Stop the instance
        """
        if self._runner is None:
            return
        await self._runner.cleanup()
        self._runner = None
        self._impl = None
        self._port = None
        self._started = False
        self._ev_loop.stop()

    def _start_web_app(self):
        """
         Start the Humming Web App
        """
        self._ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._ev_loop)
        self._ev_loop.run_until_complete(self._start())
        self._ev_loop.run_forever()

    def start(self):
        """
         Start the Humming Web App in a thread-safe way
        """
        if self.started:
            self.stop()
        thread = Thread(target=self._start_web_app)
        thread.daemon = True
        thread.start()

    def stop(self):
        """
         Stop the Humming Web App
        """
        asyncio.run_coroutine_threadsafe(self._stop(), self._ev_loop)
