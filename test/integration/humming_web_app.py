#!/usr/bin/env python

import asyncio
from aiohttp import web, ClientSession
import logging
import random
from typing import Optional
import unittest.mock
from yarl import URL
from collections import namedtuple
import requests
from threading import Thread
import json

StockResponse = namedtuple("StockResponse", "method host path params is_json response")


def get_open_port() -> int:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


class HummingWebApp:
    TEST_RESPONSE = f"hello {str(random.randint(0, 10000000))}"
    __instance = None
    _hosts_to_mock = {}
    host = "127.0.0.1"
    _port: Optional[int] = None

    @staticmethod
    def get_instance():
        if HummingWebApp.__instance is None:
            HummingWebApp()
        return HummingWebApp.__instance

    def __init__(self):
        if HummingWebApp.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            HummingWebApp.__instance = self
        self._ev_loop: None
        self._impl: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._started: bool = False
        self._stock_responses = []
        self.host = "127.0.0.1"

    async def _handler(self, request: web.Request):
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
        ws = [ws for path, ws in self._ws_response.items() if ws_path in path][0]
        await ws.send_str(message)

    async def send_ws_json(self, ws_path, data):
        ws = [ws for path, ws in self._ws_response.items() if ws_path in path][0]
        await ws.send_json(data=data)

    # To add or update data which will later be respoonded to a request according to its method, host and path
    def update_response(self, method, host, path, data, params=None, is_json=True):
        method = method.upper()
        resp_data = [x for x in self._stock_responses if x.method == method and x.host == host and x.path == path
                     and x.params == params]
        if resp_data:
            self._stock_responses.remove(resp_data[0])
        self._stock_responses.append(StockResponse(method, host, path, params, is_json, data))

    def add_host_to_mock(self, host, ignored_paths=[]):
        HummingWebApp._hosts_to_mock[host] = ignored_paths

    # reroute a url if it is one of the hosts we handle.
    @staticmethod
    def reroute_local(url):
        a_url = URL(url)
        if a_url.host in HummingWebApp._hosts_to_mock and not any(x in a_url.path for x in
                                                                  HummingWebApp._hosts_to_mock[a_url.host]):
            host_path = f"/{a_url.host}{a_url.path}"
            query = a_url.query
            a_url = a_url.with_scheme("http").with_host(HummingWebApp.host).with_port(HummingWebApp._port)\
                .with_path(host_path).with_query(query)
        return a_url

    orig_session_request = requests.Session.request

    # self here is not an instance of HummingWebApp, it is for mocking Session.request
    @staticmethod
    def reroute_request(self, method, url, **kwargs):
        a_url = HummingWebApp.reroute_local(url)
        return HummingWebApp.orig_session_request(self, method, str(a_url), **kwargs)

    @property
    def started(self) -> bool:
        return self._started

    @property
    def port(self) -> Optional[int]:
        return type(self)._port

    async def _start(self):
        try:
            HummingWebApp._port = get_open_port()
            self._impl: Optional[web.Application] = web.Application()
            self._impl.add_routes([web.route("*", '/{tail:.*}', self._handler)])
            self._runner = web.AppRunner(self._impl)
            await self._runner.setup()
            site = web.TCPSite(self._runner, host=HummingWebApp.host, port=HummingWebApp._port)
            await site.start()
            self._started = True
        except Exception:
            logging.error("oops!", exc_info=True)

    def _wait_til_started(self):
        future = asyncio.run_coroutine_threadsafe(self.wait_til_started(), self._ev_loop)
        return future.result()

    async def wait_til_started(self):
        while not self._started:
            await asyncio.sleep(0.1)

    async def _stop(self):
        if self._runner is None:
            return
        await self._runner.cleanup()
        self._runner = None
        self._impl = None
        self._port = None
        self._started = False
        self._ev_loop.stop()

    def _start_web_app(self):
        self._ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._ev_loop)
        self._ev_loop.run_until_complete(self._start())
        self._ev_loop.run_forever()

    def start(self):
        if self.started:
            self.stop()
        thread = Thread(target=self._start_web_app)
        thread.daemon = True
        thread.start()

    def stop(self):
        asyncio.run_coroutine_threadsafe(self._stop(), self._ev_loop)


class HummingWebAppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        cls.web_app: HummingWebApp = HummingWebApp.get_instance()
        cls.host = "www.google.com"
        cls.web_app.add_host_to_mock(cls.host)
        cls.web_app.update_response("get", cls.host, "/", data=cls.web_app.TEST_RESPONSE, is_json=False)
        cls.web_app.start()
        cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
        cls._patcher = unittest.mock.patch("aiohttp.client.URL")
        cls._url_mock = cls._patcher.start()
        cls._url_mock.side_effect = HummingWebApp.reroute_local

        cls._req_patcher = unittest.mock.patch.object(requests.Session, "request", autospec=True)
        cls._req_url_mock = cls._req_patcher.start()
        cls._req_url_mock.side_effect = HummingWebApp.reroute_request

    @classmethod
    def tearDownClass(cls) -> None:
        cls.web_app.stop()
        cls._patcher.stop()
        cls._req_patcher.stop()

    async def _test_web_app_response(self):
        async with ClientSession() as client:
            async with client.get("http://www.google.com/") as resp:
                text: str = await resp.text()
                print(text)
                self.assertEqual(self.web_app.TEST_RESPONSE, text)

    def test_web_app_response(self):
        self.ev_loop.run_until_complete(self._test_web_app_response())

    def test_get_request_response(self):
        r = requests.get("http://www.google.com/")
        self.assertEqual(self.web_app.TEST_RESPONSE, r.text)

    def test_update_response(self):
        self.web_app.update_response('get', 'www.google.com', '/', {"a": 1, "b": 2})
        r = requests.get("http://www.google.com/")
        r_json = json.loads(r.text)
        self.assertEqual(r_json["a"], 1)

        self.web_app.update_response('post', 'www.google.com', '/', "default")
        self.web_app.update_response('post', 'www.google.com', '/', {"a": 1, "b": 2}, params={"para_a": '11'})
        r = requests.post("http://www.google.com/", data={"para_a": 11, "para_b": 22})
        r_json = json.loads(r.text)
        self.assertEqual(r_json["a"], 1)

    def test_query_string(self):
        self.web_app.update_response('get', 'www.google.com', '/', "default")
        self.web_app.update_response('get', 'www.google.com', '/', {"a": 1}, params={"qs1": "1"})
        r = requests.get("http://www.google.com/?qs1=1")
        r_json = json.loads(r.text)
        self.assertEqual(r_json["a"], 1)


if __name__ == '__main__':
    unittest.main()
