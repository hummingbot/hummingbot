import asyncio
import json
import unittest
from typing import Awaitable

import aiohttp
from aioresponses import aioresponses

from hummingbot.core.web_assistant.connections.data_types import (
    RESTMethod, RESTResponse, EndpointRESTRequest
)


class DataTypesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_method_to_str(self):
        method = RESTMethod.GET
        method_str = str(method)

        self.assertEqual("GET", method_str)

    @aioresponses()
    def test_rest_response_properties(self, mocked_api):
        url = "https://some.url"
        body = {"one": 1}
        body_str = json.dumps(body)
        headers = {"content-type": "application/json"}
        mocked_api.get(url=url, body=body_str, headers=headers)
        aiohttp_response = self.async_run_with_timeout(aiohttp.ClientSession().get(url))

        response = RESTResponse(aiohttp_response)

        self.assertEqual(url, response.url)
        self.assertEqual(RESTMethod.GET, response.method)
        self.assertEqual(200, response.status)
        self.assertEqual(headers, response.headers)

        json_ = self.async_run_with_timeout(response.json())

        self.assertEqual(body, json_)

        text = self.async_run_with_timeout(response.text())

        self.assertEqual(body_str, text)

    @aioresponses()
    def test_rest_response_repr(self, mocked_api):
        url = "https://some.url"
        body = {"one": 1}
        body_str = json.dumps(body)
        headers = {"content-type": "application/json"}
        mocked_api.get(url=url, body=body_str, headers=headers)
        aiohttp_response = self.async_run_with_timeout(aiohttp.ClientSession().get(url))

        response = RESTResponse(aiohttp_response)

        expected = (
            f"RESTResponse(url='{url}', method={RESTMethod.GET}, status=200, headers={aiohttp_response.headers})"
        )
        actual = str(response)

        self.assertEqual(expected, actual)


class EndpointRESTRequestDummy(EndpointRESTRequest):
    @property
    def base_url(self) -> str:
        return "https://some.url"


class EndpointRESTRequestTest(unittest.TestCase):
    def test_constructs_url_from_endpoint(self):
        endpoint = "some/endpoint"
        alt_endpoint = "/some/endpoint"
        request = EndpointRESTRequestDummy(method=RESTMethod.GET, endpoint=endpoint)
        alt_request = EndpointRESTRequestDummy(method=RESTMethod.GET, endpoint=alt_endpoint)

        url = request.url
        alt_url = alt_request.url

        self.assertEqual(f"{request.base_url}/{endpoint}", url)
        self.assertEqual(url, alt_url)

    def test_raises_on_no_url_and_no_endpoint(self):
        with self.assertRaises(ValueError):
            EndpointRESTRequestDummy(method=RESTMethod.GET)

    def test_raises_on_params_supplied_to_post_request(self):
        endpoint = "some/endpoint"
        params = {"one": 1}

        with self.assertRaises(ValueError):
            EndpointRESTRequestDummy(
                method=RESTMethod.POST,
                endpoint=endpoint,
                params=params,
            )

    def test_data_to_str(self):
        endpoint = "some/endpoint"
        data = {"one": 1}

        request = EndpointRESTRequestDummy(
            method=RESTMethod.POST,
            endpoint=endpoint,
            data=data,
        )

        self.assertIsInstance(request.data, str)
        self.assertEqual(data, json.loads(request.data))

    def test_raises_on_data_supplied_to_non_post_request(self):
        endpoint = "some/endpoint"
        data = {"one": 1}

        with self.assertRaises(ValueError):
            EndpointRESTRequestDummy(
                method=RESTMethod.GET,
                endpoint=endpoint,
                data=data,
            )
