import functools
import asyncio
import aresponses
import sys
import requests_mock
from aresponses.main import ClientRequest
from yarl import URL

mock_api_test_mode_config = True
PASSTHROUGH = "PASSTHROUGH"


def mock_aiohttp(params):
    def decorator_mock_aiohttp(func):
        @functools.wraps(func)
        def wrapper_mock_aiohttp(*args, **kwargs):
            if not mock_api_test_mode_config:
                return func(*args, **kwargs)
            loop = asyncio.get_event_loop()
            arsps = aresponses.ResponsesMockServer()
            loop.run_until_complete(arsps.__aenter__())
            for param in params:
                host, path, method, response = param
                if response.lower() == PASSTHROUGH:
                    async def pass_through(*args):
                        return await arsps.passthrough(ClientRequest(url=URL(f"https://{host}{path}"), method=method))
                    response = pass_through
                else:
                    response = aresponses.Response(
                        body=response,
                        headers={"Content-Type": "application/json"})
                arsps.add(host, path, method, response)
            value = func(*args, **kwargs)
            loop.run_until_complete(arsps.__aexit__(*sys.exc_info()))
            return value
        return wrapper_mock_aiohttp
    return decorator_mock_aiohttp


def mock_requests(host, path, response):
    def decorator_mock_requests(func):
        @functools.wraps(func)
        def wrapper_mock_requests(*args, **kwargs):
            if not mock_api_test_mode_config:
                return func(*args, **kwargs)
            with requests_mock.mock() as req_mock:
                req_mock.get(host + path, text=response)
                value = func(*args, **kwargs)
            return value
        return wrapper_mock_requests
    return decorator_mock_requests
