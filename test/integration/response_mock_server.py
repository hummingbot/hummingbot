import asyncio
import logging
from functools import partial
import re
from aiohttp import web, ClientSession
from aiohttp.web import Response
from aiohttp.client_reqrep import ClientRequest
from aiohttp.connector import TCPConnector
from aiohttp.helpers import sentinel
from aiohttp.test_utils import BaseTestServer
from aiohttp.web_response import StreamResponse
from aiohttp.web_runner import ServerRunner
from aiohttp.web_server import Server
import unittest
from hummingbot.core.utils.ssl_client_request import SSLClientRequest
import requests

logger = logging.getLogger(__name__)


ANY = re.compile(".*")

def _text_matches_pattern(pattern, text):
    # This is needed for compatibility with old Python versions
    try:
        pattern_class = re.Pattern
    except AttributeError:
        pattern_class = re._pattern_type
    if isinstance(pattern, str):
        if pattern == text:
            return True
    elif isinstance(pattern, pattern_class):
        if pattern.search(text):
            return True
    return False


class RawResponse(StreamResponse):
    """
    Allow complete control over the response
    Useful for mocking invalid responses
    """

    def __init__(self, body):
        super().__init__()
        self._body = body

    async def _start(self, request, *_, **__):
        self._req = request
        self._keep_alive = False
        writer = self._payload_writer = request._payload_writer
        return writer

    async def write_eof(self, *_, **__):
        await super().write_eof(self._body)


class ResponsesMockServer(BaseTestServer):
    ANY = ANY
    Response = web.Response
    RawResponse = RawResponse

    def __init__(self, *, scheme=sentinel, host="127.0.0.1", **kwargs):
        self._responses = []
        self._host_patterns = set()
        self._exception = None
        self._started = False
        super().__init__(scheme=scheme, host=host, **kwargs)

    @property
    def started(self) -> bool:
        return self._started

    async def _make_runner(self, debug=True, **kwargs):
        srv = Server(self._handler, loop=self._loop, debug=True, **kwargs)
        return ServerRunner(srv, debug=debug, **kwargs)

    async def _close_hook(self):
        return

    async def _handler(self, request):
        return await self._find_response(request)

    def add(self, host, path=ANY, method=ANY, response="", api_response="", match_querystring=False):
        if isinstance(host, str):
            host = host.lower()

        if isinstance(method, str):
            method = method.lower()

        self._host_patterns.add(host)
        resp = response
        if api_response != "":
            resp = Response(body=api_response, headers={"Content-Type": "application/json"})
        self._responses.append((host, path, method, resp, match_querystring))

    def _host_matches(self, match_host):
        match_host = match_host.lower()
        for host_pattern in self._host_patterns:
            if _text_matches_pattern(host_pattern, match_host):
                return True

        return False

    async def _find_response(self, request):
        print(f"request: {request.url}")
        return await self.passthrough(request)
        host, path, path_qs, method = request.host, request.path, request.path_qs, request.method
        logger.info(f"Looking for match for {host} {path} {method}")  # noqa
        i = 0
        host_matched = False
        path_matched = False
        for host_pattern, path_pattern, method_pattern, response, match_querystring in self._responses:
            if _text_matches_pattern(host_pattern, host):
                host_matched = True
                if (not match_querystring and _text_matches_pattern(path_pattern, path)) or (
                    match_querystring and _text_matches_pattern(path_pattern, path_qs)
                ):
                    path_matched = True
                    if _text_matches_pattern(method_pattern, method.lower()):
                        # del self._responses[i]

                        if callable(response):
                            if asyncio.iscoroutinefunction(response):
                                return await response(request)
                            return response(request)

                        if isinstance(response, str):
                            return self.Response(body=response)

                        return response
            i += 1
        return await self.passthrough(request)
        self._exception = Exception(f"No Match found for {host} {path} {method}.  Host Match: {host_matched}  Path Match: {path_matched}")
        # self._loop.stop()
        raise self._exception  # noqa

    async def passthrough(self, request):
        resp = requests.request(request.method, str(request.url).replace('http', 'https'))
        response = self.Response(body=resp.text, status=resp.status_code, headers=resp.headers)
        return response
        """Make non-mocked network request"""
        connector = TCPConnector()
        connector._resolve_host = partial(self._old_resolver_mock, connector)

        new_is_ssl = ClientRequest.is_ssl
        ClientRequest.is_ssl = self._old_is_ssl
        ClientRequest.__init__ = self._old_init
        try:
            original_request = request.clone(scheme="https" if request.headers["AResponsesIsSSL"] else "http")
            print(f"passthrough:{original_request.url}")

            headers = {k: v for k, v in request.headers.items() if k != "AResponsesIsSSL"}

            async with ClientSession(connector=connector, request_class=SSLClientRequest) as session:
                async with getattr(session, request.method.lower())(original_request.url, headers=headers, data=(await request.read())) as r:
                    headers = {k: v for k, v in r.headers.items() if k.lower() == "content-type"}
                    data = await r.read()
                    response = self.Response(body=data, status=r.status, headers=headers)
                    return response
        # except Exception as ex:
        #     print(str(ex))
        finally:
            ClientRequest.is_ssl = new_is_ssl
            # self._old_init = ClientRequest.__init__

    async def _start(self):
        await self.start_server(loop=self._loop)

        self._old_resolver_mock = TCPConnector._resolve_host

        async def _resolver_mock(_self, host, port, traces=None):
            return [{"hostname": host, "host": "127.0.0.1", "port": self.port, "family": _self._family, "proto": 0, "flags": 0}]

        TCPConnector._resolve_host = _resolver_mock

        self._old_is_ssl = ClientRequest.is_ssl

        def new_is_ssl(_self):
            return False

        ClientRequest.is_ssl = new_is_ssl

        # store whether a request was an SSL request in the `AResponsesIsSSL` header
        self._old_init = ClientRequest.__init__

        def new_init(_self, *largs, **kwargs):
            self._old_init(_self, *largs, **kwargs)

            is_ssl = "1" if self._old_is_ssl(_self) else ""
            _self.update_headers({**_self.headers, "AResponsesIsSSL": is_ssl})

        ClientRequest.__init__ = new_init
        self._started = True
        return self

    async def wait_til_started(self):
        while not self._started:
            await asyncio.sleep(0.1)

    async def _stop(self):
        TCPConnector._resolve_host = self._old_resolver_mock
        ClientRequest.is_ssl = self._old_is_ssl
        await self.close()

    def start(self):
        asyncio.ensure_future(self._start())

    def stop(self):
        asyncio.ensure_future(self._stop())


class ResponseMockSeverTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.TEST_RESPONSE = 'hi there!!'
        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        cls.mock_server: ResponsesMockServer = ResponsesMockServer(loop=cls.ev_loop)
        cls.mock_server.add('python.org', '/', 'get', cls.TEST_RESPONSE)
        cls.mock_server.add('www.google.com', '/', 'get', cls.mock_server.passthrough)
        cls.mock_server.start()
        cls.ev_loop.run_until_complete(cls.mock_server.wait_til_started())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.mock_server.stop()

    async def _test_mock_server_response(self):
        async with ClientSession() as client:
            async with client.get('http://python.org') as resp:
                text: str = await resp.text()
                self.assertEqual(self.TEST_RESPONSE, text)

    def test_mock_server_response(self):
        self.ev_loop.run_until_complete(self._test_mock_server_response())

    async def _test_pass_through(self):
        async with ClientSession() as client:
            async with client.get('http://www.google.com/') as resp:
                text: str = await resp.text()
                self.assertGreater(len(text), 100)

    def test_pass_through(self):
        self.ev_loop.run_until_complete(self._test_pass_through())

    async def _test_not_registered_pass_through(self):
        url = 'https://api.liquid.com/products'
        async with ClientSession() as client:
            async with client.get(url) as resp:
                text: str = await resp.text()
                print(f"{url}: {text}")
                self.assertGreater(len(text), 100)

    def test_not_registered_pass_through(self):
        self.ev_loop.run_until_complete(self._test_not_registered_pass_through())

if __name__ == '__main__':
    unittest.main()