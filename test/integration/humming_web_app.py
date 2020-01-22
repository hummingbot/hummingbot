#!/usr/bin/env python

import asyncio
from aiohttp import web, ClientSession
import logging
import random
from typing import Optional
import unittest
from unittest import mock
from yarl import URL
from collections import namedtuple

ResponseData = namedtuple("ResponseData", "method host path query_string is_permanent is_json data")


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

    def __init__(self):
        self._ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self._impl: Optional[web.Application] = web.Application()
        self._runner: Optional[web.AppRunner] = None
        self._port: Optional[int] = None
        self._started: bool = False
        self._responses_data = []
        self.host = "127.0.0.1"
        self._hosts_to_handle = {}

    async def _handler(self, request: web.Request):
        method, req_path, query_string = request.method, request.path, request.query_string
        req_path = req_path[1:]
        host = req_path[0:req_path.find("/")]
        path = req_path[req_path.find("/"):]
        resp_data = [x for x in self._responses_data if x.method == method and x.host == host and x.path == path and
                     x.query_string == query_string]
        if not resp_data:
            raise web.HTTPNotFound(text=f"No Match found for {host}{path} {method}")
        is_json, data = resp_data[0].is_json, resp_data[0].data
        if not resp_data[0].is_permanent:
            self._responses_data.remove(resp_data[0])
        if is_json:
            return web.json_response(data=data)
        else:
            return web.Response(text=data)

    # To add or update data which will later be respoonded to a request according to its method, host and path
    def update_response_data(self, method, host, path, data, query_string="", is_permanent=False, is_json=True):
        method = method.upper()
        resp_data = [x for x in self._responses_data if x.method == method and x.host == host and x.path == path]
        if resp_data:
            self._responses_data.remove(resp_data[0])
        self._responses_data.append(ResponseData(method, host, path, query_string, is_permanent, is_json, data))

    def add_host_to_handle(self, host, ignored_paths=[]):
        self._hosts_to_handle[host] = ignored_paths

    # reroute a url if it is one of the hosts we handle.
    def reroute_local(self, url):
        a_url = URL(url)
        if a_url.host in self._hosts_to_handle and not any(x in a_url.path for x in self._hosts_to_handle[a_url.host]):
            host_path = f"/{a_url.host}{a_url.path}"
            query = a_url.query
            a_url = a_url.with_scheme("http").with_host(self.host).with_port(self.port).with_path(host_path)\
                .with_query(query)
        return a_url

    @property
    def started(self) -> bool:
        return self._started

    @property
    def port(self) -> Optional[int]:
        return self._port

    async def _start(self):
        try:
            # add a handler to all requests coming to this local host and on the port
            self._impl.add_routes([web.route("*", '/{tail:.*}', self._handler)])
            self._runner = web.AppRunner(self._impl)
            await self._runner.setup()
            site = web.TCPSite(self._runner, host=self.host, port=self.port)
            await site.start()
            self._started = True
        except Exception:
            logging.error("oops!", exc_info=True)

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

    def start(self):
        if self.started:
            self.stop()
        self._port = get_open_port()
        asyncio.ensure_future(self._start())

    def stop(self):
        asyncio.ensure_future(self._stop())


class HummingWebAppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        cls.web_app: HummingWebApp = HummingWebApp()
        cls.host = "www.google.com"
        cls.web_app.add_host_to_handle(cls.host)
        cls.web_app.update_response_data("get", cls.host, "/", data=cls.web_app.TEST_RESPONSE, is_json=False)
        cls.web_app.start()
        cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
        cls._patcher = unittest.mock.patch("aiohttp.client.URL")
        cls._url_mock = cls._patcher.start()
        cls._url_mock.side_effect = cls.web_app.reroute_local

    @classmethod
    def tearDownClass(cls) -> None:
        cls.web_app.stop()
        cls._patcher.stop()

    async def _test_web_app_response(self):
        async with ClientSession() as client:
            async with client.get("http://www.google.com/") as resp:
                text: str = await resp.text()
                print(text)
                self.assertEqual(self.web_app.TEST_RESPONSE, text)

    def test_web_app_response(self):
        self.ev_loop.run_until_complete(self._test_web_app_response())


if __name__ == '__main__':
    unittest.main()