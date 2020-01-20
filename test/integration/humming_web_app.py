#!/usr/bin/env python

import asyncio
from aiohttp import web, ClientSession
import logging
import random
from typing import Optional
import unittest
from yarl import URL

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
        self._json_responses = {}
        self.host = "127.0.0.1"
        self._host_paths_to_handle = []

    async def _handle(self, request: web.Request):
        json_resp = self._json_responses[request.path]
        return web.json_response(data=json_resp)

    def add_json_response(self, host_path, json_resp):
        # json_resp = json_resp.replace("\n", "")
        host_path = "/" + host_path
        self._json_responses[host_path] = json_resp
        self._impl.add_routes([web.get(host_path, self._handle)])
        self._host_paths_to_handle.append(host_path)

    def reroute_local(self, url):
        a_url = URL(url)
        host_path = f"/{a_url.host}{a_url.path}"
        query = a_url.query
        if host_path not in self._host_paths_to_handle:
            return a_url
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
            self._impl.add_routes([
                web.get("/*", self._handle)
            ])
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


class JenkinsWebAppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        cls.web_app: HummingWebApp = HummingWebApp()
        cls.web_app.add_json_response("/get_json", '{text="retuned json"}')
        cls.web_app.start()
        cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.web_app.stop()

    async def _test_web_app_response(self):
        async with ClientSession() as client:
            async with client.get(f"http://127.0.0.1:{self.web_app.port}/get_json") as resp:
                text: str = await resp.text()
                print(text)
                self.assertIn("json", text)
                # self.assertEqual(self.web_app.TEST_RESPONSE, text)

    def test_web_app_response(self):
        self.ev_loop.run_until_complete(self._test_web_app_response())


if __name__ == '__main__':
    unittest.main()