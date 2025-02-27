import json
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

import aiohttp
from aioresponses import aioresponses

from hummingbot.core.web_assistant.connections.data_types import EndpointRESTRequest, RESTMethod, RESTResponse


class DataTypesTest(IsolatedAsyncioWrapperTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

    def test_rest_method_to_str(self):
        method = RESTMethod.GET
        method_str = str(method)

        self.assertEqual("GET", method_str)

    @aioresponses()
    async def test_rest_response_properties(self, mocked_api):
        url = "https://some.url"
        body = {"one": 1}
        body_str = json.dumps(body)
        headers = {"content-type": "application/json"}
        mocked_api.get(url=url, body=body_str, headers=headers)
        aiohttp_client_session = aiohttp.ClientSession()
        aiohttp_response = await (aiohttp_client_session.get(url))

        response = RESTResponse(aiohttp_response)

        self.assertEqual(url, response.url)
        self.assertEqual(RESTMethod.GET, response.method)
        self.assertEqual(200, response.status)
        self.assertEqual(headers, response.headers)

        json_ = await (response.json())

        self.assertEqual(body, json_)

        text = await (response.text())

        self.assertEqual(body_str, text)
        await (aiohttp_client_session.close())

    @aioresponses()
    async def test_rest_response_with_test_properties(self, mocked_api):
        url = "https://some.url"
        data = '{"one": 1}'
        data_str = data.encode("utf-8")
        body = f'{data_str}'
        body_str = json.dumps(body)
        headers = {"content-type": "text/html"}
        mocked_api.get(url=url, body=body_str, headers=headers)
        aiohttp_client_session = aiohttp.ClientSession()
        aiohttp_response = await (aiohttp_client_session.get(url))

        response = RESTResponse(aiohttp_response)

        self.assertEqual(url, response.url)
        self.assertEqual(RESTMethod.GET, response.method)
        self.assertEqual(200, response.status)
        self.assertEqual(headers, response.headers)

        json_ = await (response.json())

        self.assertEqual(body, json_)

    @aioresponses()
    async def test_rest_response_repr(self, mocked_api):
        url = "https://some.url"
        body = {"one": 1}
        body_str = json.dumps(body)
        headers = {"content-type": "application/json"}
        mocked_api.get(url=url, body=body_str, headers=headers)
        aiohttp_client_session = aiohttp.ClientSession()
        aiohttp_response = await (aiohttp_client_session.get(url))

        response = RESTResponse(aiohttp_response)

        expected = (
            f"RESTResponse(url='{url}', method={RESTMethod.GET}, status=200, headers={aiohttp_response.headers})"
        )
        actual = str(response)

        self.assertEqual(expected, actual)
        await (aiohttp_client_session.close())


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
