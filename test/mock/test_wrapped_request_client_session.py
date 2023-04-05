import asyncio
import functools
import unittest
from test.mock.wrapped_request_client_session import WrappedRequestClientSession

import aiohttp
from aiohttp import ClientResponse, ClientSession
from aiohttp.test_utils import TestServer


class CustomClientResponse(ClientResponse):
    pass


class TestWrappedRequestClientSession(unittest.TestCase):

    def test_init_with_incorrect_response_class_subclass(self):
        class NotClientResponseSubclass:
            pass

        with self.assertRaises(ValueError):
            WrappedRequestClientSession(response_class=NotClientResponseSubclass)  # type: ignore

    def test_async_context_manager(self):
        async def async_test():
            async with WrappedRequestClientSession() as session:
                self.assertIsInstance(session._session, ClientSession)

        asyncio.run(async_test())

    def test_wrapped_request(self):
        async def request_wrapper(session, *args, **kwargs):
            return await session.client_session_request(*args, **kwargs)

        async def async_test():
            async with WrappedRequestClientSession() as session:
                url = "http://example.com"
                wrapped_request_wrapper = functools.partial(request_wrapper, session)
                response = await wrapped_request_wrapper("GET", url)
                self.assertIsInstance(response, ClientResponse)

        asyncio.run(async_test())

    def test_request_wrapper_raises(self):
        async def async_test():
            async with WrappedRequestClientSession() as session:
                with self.assertRaises(NotImplementedError):
                    await session.get("http://example.com")

        asyncio.run(async_test())

    def test_missing_wrapped_session_in_custom_request_wrapper_is_added(self):
        async def handler(request):
            return aiohttp.web.Response(text="GET response")

        app = aiohttp.web.Application()
        app.router.add_route("GET", "/", handler)

        async def custom_request_wrapper(*args, **kwargs):
            self.assertTrue("wrapped_session" in kwargs)
            return await kwargs["wrapped_session"].client_session_request(*args, **kwargs)

        async def async_test():
            async with TestServer(app) as server, WrappedRequestClientSession(
                    request_wrapper=custom_request_wrapper
            ) as session:
                url = str(server.make_url("/"))
                response = await session.get(url)
                self.assertIsInstance(response, ClientResponse)
                text = await response.text()
                self.assertEqual(text, "GET response")

        asyncio.run(async_test())

    def test_invalid_wrapped_session(self):
        async def handler(request):
            return aiohttp.web.Response(text="GET response")

        app = aiohttp.web.Application()
        app.router.add_route("GET", "/", handler)

        async def custom_request_wrapper(*args, **kwargs):
            wrapped_session = kwargs.pop("wrapped_session", None)
            if not isinstance(wrapped_session, WrappedRequestClientSession):
                raise TypeError("Invalid wrapped_session")
            return await wrapped_session.client_session_request(*args, **kwargs)

        async def async_test():
            async with TestServer(app) as server, WrappedRequestClientSession(
                    request_wrapper=functools.partial(custom_request_wrapper, wrapped_session="invalid")
            ) as session:
                url = str(server.make_url("/"))
                response = await session.get(url)
                self.assertIsInstance(response, ClientResponse)
                text = await response.text()
                self.assertEqual(text, "GET response")

        asyncio.run(async_test())

    def test_getattr(self):
        async def async_test():
            async with WrappedRequestClientSession() as session:
                self.assertIsInstance(session.timeout, aiohttp.ClientTimeout)
                with self.assertRaises(AttributeError):
                    _ = session.__unknown_attr__

        asyncio.run(async_test())

    def test_request_integration(self):
        async def handler(request):
            return aiohttp.web.Response(text="test response")

        app = aiohttp.web.Application()
        app.router.add_route("GET", "/", handler)

        async def request_wrapper(session, *args, **kwargs):
            return await session.client_session_request(*args, **kwargs)

        async def async_test():
            async with TestServer(app) as server, WrappedRequestClientSession() as session:
                url = str(server.make_url("/"))
                wrapped_request_wrapper = functools.partial(request_wrapper, session)
                response = await wrapped_request_wrapper("GET", url)
                self.assertIsInstance(response, ClientResponse)
                text = await response.text()
                self.assertEqual(text, "test response")

        asyncio.run(async_test())

    def test_get_request(self):
        async def handler(request):
            return aiohttp.web.Response(text="GET response")

        app = aiohttp.web.Application()
        app.router.add_route("GET", "/", handler)

        async def custom_request_wrapper(*args, **kwargs):
            wrapped_session = kwargs.pop("wrapped_session")
            return await wrapped_session.client_session_request(*args, **kwargs)

        async def async_test():
            async with TestServer(app) as server, WrappedRequestClientSession(
                    request_wrapper=functools.partial(custom_request_wrapper, wrapped_session=None)
            ) as session:
                url = str(server.make_url("/"))
                response = await session.get(url)
                self.assertIsInstance(response, ClientResponse)
                text = await response.text()
                self.assertEqual(text, "GET response")

        asyncio.run(async_test())

    def test_post_request(self):
        async def handler(request):
            data = await request.post()
            return aiohttp.web.Response(text=f"POST response: {data['key']}")

        app = aiohttp.web.Application()
        app.router.add_route("POST", "/", handler)

        async def async_test():
            async with TestServer(app) as server, WrappedRequestClientSession(
                    request_wrapper=WrappedRequestClientSession.client_session_request
            ) as session:
                url = str(server.make_url("/"))
                response = await session.post(url, data={'key': 'value'})
                self.assertIsInstance(response, ClientResponse)
                text = await response.text()
                self.assertEqual(text, "POST response: value")

        asyncio.run(async_test())

    def test_request_wrapper(self):
        async def handler(request):
            return aiohttp.web.Response(text="Custom response")

        app = aiohttp.web.Application()
        app.router.add_route("GET", "/", handler)

        async def custom_request_wrapper(self, *args, **kwargs):
            response = await self.client_session_request(*args, **kwargs)
            response_class = response.__class__
            return response_class.from_client_response(response, CustomClientResponse)

        async def async_test():
            async with TestServer(app) as server:
                session = WrappedRequestClientSession()
                session.request_wrapper = custom_request_wrapper.__get__(session)
                async with session:
                    url = str(server.make_url("/"))
                    response = await session.get(url)
                    self.assertIsInstance(response, CustomClientResponse)
                    text = await response.text()
                    self.assertEqual(text, "Custom response")

        asyncio.run(async_test())

    def test_request_wrapper_exception_handling(self):
        async def handler(request):
            return aiohttp.web.Response(text="GET response")

        app = aiohttp.web.Application()
        app.router.add_route("GET", "/", handler)

        async def custom_request_wrapper(*args, **kwargs):
            raise ValueError("Test exception")

        async def async_test():
            async with TestServer(app) as server, WrappedRequestClientSession(
                    request_wrapper=custom_request_wrapper
            ) as session:
                url = str(server.make_url("/"))
                with self.assertRaises(ValueError):
                    await session.get(url)

        asyncio.run(async_test())

    def test_custom_response_class(self):
        class CustomClientResponse(ClientResponse):
            pass

        async def async_test():
            async with WrappedRequestClientSession(response_class=CustomClientResponse) as session:
                self.assertIs(session._kwargs["response_class"], CustomClientResponse)

        asyncio.run(async_test())

    def test_request_wrapper_modifies_response(self):
        async def handler(request):
            return aiohttp.web.Response(text="Original response")

        app = aiohttp.web.Application()
        app.router.add_route("GET", "/", handler)

        async def custom_request_wrapper(*args, **kwargs):
            wrapped_session = kwargs.pop("wrapped_session")
            response = await wrapped_session.client_session_request(*args, **kwargs)
            response._body = b"Modified response"
            return response

        async def async_test():
            async with TestServer(app) as server, WrappedRequestClientSession(
                    request_wrapper=custom_request_wrapper
            ) as session:
                url = str(server.make_url("/"))
                response = await session.get(url)
                text = await response.text()
                self.assertEqual(text, "Modified response")

        asyncio.run(async_test())

    def test_other_http_methods(self):
        async def handler(request):
            return aiohttp.web.Response(text=f"{request.method} response")

        app = aiohttp.web.Application()
        app.router.add_route("*", "/", handler)

        async def custom_request_wrapper(*args, **kwargs):
            wrapped_session = kwargs.pop("wrapped_session")
            response = await wrapped_session.client_session_request(*args, **kwargs)
            text = await response.text()
            if text == "PUT response":
                response._body = b"PUT Modified response"
            elif text == "DELETE response":
                response._body = b"DELETE Modified response"
            return response

        async def async_test():
            async with TestServer(app) as server, WrappedRequestClientSession(
                    request_wrapper=custom_request_wrapper
            ) as session:
                url = str(server.make_url("/"))

                response = await session.put(url)
                text = await response.text()
                self.assertEqual(text, "PUT Modified response")

                response = await session.delete(url)
                text = await response.text()
                self.assertEqual(text, "DELETE Modified response")

        asyncio.run(async_test())
