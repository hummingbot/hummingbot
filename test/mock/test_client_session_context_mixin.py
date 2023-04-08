import asyncio
import unittest
from test.mock.client_session_context_mixin import ClientSessionContextMixin, InvalidRequestWrapperError

import aiohttp
from multidict import CIMultiDict


class CustomClientResponse(aiohttp.ClientResponse):
    @property
    def headers(self) -> CIMultiDict:
        custom_headers = super().headers.copy()
        custom_headers["X-Custom-Header"] = "Custom Value"
        return custom_headers


class TestClientSessionContextMixin(unittest.TestCase):

    def setUp(self):
        self.default_mixin = ClientSessionContextMixin()

    async def async_request_wrapper(self, *args, **kwargs) -> aiohttp.ClientResponse:
        wrapped_session = kwargs.pop("wrapped_session", None)
        return await wrapped_session.client_session_request(*args, **kwargs)

    def test_mixin_without_request_wrapper_raises_error(self):
        async def _test():
            async with self.default_mixin:
                pass

        with self.assertRaises(InvalidRequestWrapperError):
            asyncio.run(_test())

        async def _test_call_without_request_wrapper():
            async with self.default_mixin():
                pass

        with self.assertRaises(InvalidRequestWrapperError):
            asyncio.run(_test_call_without_request_wrapper())

    def test_client_session_context_mixin_no_request_wrapper(self):
        async def _test():
            async with self.default_mixin as client:
                async with client.get("https://httpbin.org/get") as resp:
                    data = await resp.json()
                    self.assertEqual(resp.status, 200)
                    self.assertIn("url", data)

        with self.assertRaises(InvalidRequestWrapperError):
            asyncio.run(_test())

    def test_client_session_context_mixin_with_request_wrapper(self):
        mixin = ClientSessionContextMixin(request_wrapper=self.async_request_wrapper)

        async def _test():
            async with mixin as client:
                async with client.get("https://httpbin.org/get") as resp:
                    data = await resp.json()
                    self.assertEqual(resp.status, 200)
                    self.assertIn("url", data)

        asyncio.run(_test())

    def test_client_session_context_mixin_update_request_wrapper(self):
        async def _test():
            async with self.default_mixin as client:
                async with client.get("https://httpbin.org/get") as resp:
                    data = await resp.json()
                    self.assertEqual(resp.status, 200)
                    self.assertIn("url", data)

        with self.assertRaises(InvalidRequestWrapperError):
            asyncio.run(_test())

        async def _test_updated_wrapper():
            client = await self.default_mixin.__aenter__(request_wrapper=self.async_request_wrapper)
            async with client.get("https://httpbin.org/get") as resp:
                data = await resp.json()
                self.assertEqual(resp.status, 200)
                self.assertIn("url", data)

            client = await self.default_mixin.__aenter__(request_wrapper=self.async_request_wrapper)
            async with client.get("https://httpbin.org/get") as resp:
                data = await resp.json()
                self.assertEqual(resp.status, 200)
                self.assertIn("url", data)

        asyncio.run(_test_updated_wrapper())

    def test_client_session_context_mixin_update_response_class(self):
        mixin = ClientSessionContextMixin(request_wrapper=self.async_request_wrapper)

        class CustomResponse(aiohttp.ClientResponse):
            pass

        async def _test():
            client = await mixin.__aenter__(response_class=CustomResponse)
            async with client.get("https://httpbin.org/get") as resp:
                self.assertIsInstance(resp, CustomResponse)
                data = await resp.json()
                self.assertEqual(resp.status, 200)
                self.assertIn("url", data)

        asyncio.run(_test())

    def test_client_session_context_mixin_both_request_wrapper_and_response_class(self):
        class CustomResponse(aiohttp.ClientResponse):
            pass

        mixin = ClientSessionContextMixin(request_wrapper=self.async_request_wrapper,
                                          response_class=CustomResponse)

        async def _test():
            async with mixin as client:
                async with client.get("https://httpbin.org/get") as resp:
                    self.assertIsInstance(resp, CustomResponse)
                    data = await resp.json()
                    self.assertEqual(resp.status, 200)
                    self.assertIn("url", data)

        asyncio.run(_test())

    def test_mixin_with_custom_response_class(self):
        class CustomResponse(aiohttp.ClientResponse):
            pass

        async def _test():
            async with self.default_mixin(request_wrapper=self.async_request_wrapper,
                                          response_class=CustomResponse) as client:
                async with client.get("https://httpbin.org/get") as resp:
                    self.assertIsInstance(resp, CustomResponse)
                    data = await resp.json()
                    self.assertEqual(resp.status, 200)
                    self.assertIn("url", data)

            async with self.default_mixin(response_class=aiohttp.ClientResponse) as client:
                async with client.get("https://httpbin.org/get") as resp:
                    self.assertNotIsInstance(resp, CustomResponse)
                    self.assertIsInstance(resp, aiohttp.ClientResponse)
                    data = await resp.json()
                    self.assertEqual(resp.status, 200)
                    self.assertIn("url", data)

        asyncio.run(_test())

    def test_mixin_with_custom_response_class_update_request_wrapper(self):
        async def custom_request_wrapper(*args, **kwargs) -> aiohttp.ClientResponse:
            wrapped_session = kwargs.pop("wrapped_session", None)
            resp = await wrapped_session.client_session_request(*args, **kwargs)
            resp.headers["X-Custom-Header"] = "Custom Value"
            return resp

        async def _test():
            async with self.default_mixin(request_wrapper=self.async_request_wrapper) as client:
                async with client.get("https://httpbin.org/get") as resp:
                    data = await resp.json()
                    self.assertEqual(resp.status, 200)
                    self.assertIn("url", data)
                    self.assertNotIn("X-Custom-Header", resp.headers)

            async with self.default_mixin(response_class=CustomClientResponse, request_wrapper=custom_request_wrapper) as client:
                async with client.get("https://httpbin.org/get") as resp:
                    data = await resp.json()
                    self.assertEqual(resp.status, 200)
                    self.assertIn("url", data)
                    self.assertIn("X-Custom-Header", resp.headers)
                    self.assertEqual("Custom Value", resp.headers["X-Custom-Header"])

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
