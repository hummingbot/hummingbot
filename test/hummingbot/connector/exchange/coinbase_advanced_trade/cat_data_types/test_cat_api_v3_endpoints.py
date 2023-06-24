from dataclasses import dataclass, field
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict
from unittest.mock import patch

import hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_request_types as request_data_types
import hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_response_types as response_data_types
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_endpoints import (
    CoinbaseAdvancedTradeAPIEndpoint,
    CoinbaseAdvancedTradeAPIEndpointException,
    CoinbaseAdvancedTradeAPIVersionEnum as _APIVersion,
)
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class MockAPICall:
    async def api_post(self, *args, **kwargs) -> Dict[str, Any]:
        # Mock response for API post
        return {"method": "POST", "status": f"ok - api_post called with {args} {kwargs}"}

    async def api_get(self, *args, **kwargs) -> Dict[str, Any]:
        # Mock response for API get
        return {"method": "GET", "status": f"ok - api_get called with {args} {kwargs}"}

    async def api_delete(self, *args, **kwargs) -> Dict[str, Any]:
        # Mock response for API get
        return {"method": "DELETE", "status": f"ok - api_delete called with {args} {kwargs}"}


@dataclass
class MockRequest:
    BASE_ENDPOINT: str = "Mocked"
    endpoint_: str = "mocked"
    data_: Dict = field(default_factory=dict)
    params_: Dict = field(default_factory=dict)
    is_auth_required_: bool = False

    @classmethod
    def limit_id(cls) -> str:
        return "Mocked"

    def base_endpoint(self) -> str:
        return "Mocked/" + self.endpoint_

    @classmethod
    def method(cls) -> RESTMethod:
        return RESTMethod.DELETE

    def add_rate_limit(self, url_base: str):
        pass

    def data(self) -> Dict:
        return self.data_

    def params(self) -> Dict:
        return self.params_

    def is_auth_required(self) -> bool:
        return self.is_auth_required_


@dataclass
class MockResponse:
    method: RESTMethod
    status: str


class TestCoinbaseAdvancedTradeAPIEndpoint(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        self.api_call = MockAPICall()

        self.request_class = MockRequest
        self.response_class = MockResponse

    async def run_execute_test(self,
                               api_method="api_delete",
                               *,
                               method=RESTMethod.DELETE,
                               endpoint="mock_endpoint",
                               data=None,
                               params=None,
                               is_auth_required=False,
                               limit_id="Mocked"):
        @patch.object(request_data_types.CoinbaseAdvancedTradeRequest, 'find_class_by_name')
        @patch.object(response_data_types.CoinbaseAdvancedTradeResponse, 'find_class_by_name')
        async def test(mock_get_response_class, mock_get_request_class):
            mock_get_request_class.return_value = MockRequest
            mock_get_response_class.return_value = MockResponse

            endpoint_instance = CoinbaseAdvancedTradeAPIEndpoint(self.api_call, _APIVersion.V3, "mock_request",
                                                                 # These are passed to the request instantiation
                                                                 endpoint_=endpoint,
                                                                 data_=data,
                                                                 params_=params,
                                                                 is_auth_required_=is_auth_required,
                                                                 )
            # Classes are correctly set
            self.assertEqual(endpoint_instance.request_class, MockRequest)
            self.assertEqual(endpoint_instance.response_class, MockResponse)

            # Request is correctly instantiated
            self.assertIsInstance(endpoint_instance.request, MockRequest)
            self.assertEqual(endpoint_instance.request.base_endpoint(), "Mocked/" + endpoint)
            self.assertEqual(endpoint_instance.request.data(), data)
            self.assertEqual(endpoint_instance.request.params(), params)
            self.assertEqual(endpoint_instance.request.is_auth_required(), is_auth_required)
            self.assertEqual(endpoint_instance.request.limit_id(), limit_id)

            response: MockResponse = await endpoint_instance.execute()  # type: ignore # forcing MockResponse

            # self.assertEqual(response.method, method.value)
            self.assertEqual(f"ok - api_delete called with "
                             "() {'path_url': "
                             # Concatenate the base url and the request.endpoint
                             f"'Mocked/{endpoint}'"
                             f", 'data': "
                             f"{data}"
                             f", 'params': "
                             f"{params}"
                             f", 'is_auth_required': "
                             f"{is_auth_required}"
                             f", 'limit_id': "
                             f"'{limit_id}'"
                             "}", response.status)

        await test()

    @patch.object(request_data_types.CoinbaseAdvancedTradeRequest, 'find_class_by_name')
    @patch.object(response_data_types.CoinbaseAdvancedTradeResponse, 'find_class_by_name')
    def test_endpoint_creation(self, mock_get_response_class, mock_get_request_class):
        mock_get_request_class.return_value = self.request_class
        mock_get_response_class.return_value = self.response_class

        endpoint = CoinbaseAdvancedTradeAPIEndpoint(self.api_call, _APIVersion.V3, "mock_request")

        self.assertEqual(endpoint.request_class, self.request_class)
        self.assertEqual(endpoint.response_class, self.response_class)

    @patch.object(MockRequest, 'add_rate_limit')
    @patch.object(request_data_types.CoinbaseAdvancedTradeRequest, 'find_class_by_name')
    @patch.object(response_data_types.CoinbaseAdvancedTradeResponse, 'find_class_by_name')
    async def test_execute_default(self, mock_get_response_class, mock_get_request_class, mock_request_add_rate_limit):
        mock_get_request_class.return_value = self.request_class
        mock_get_response_class.return_value = self.response_class
        default_request = self.request_class()

        endpoint = CoinbaseAdvancedTradeAPIEndpoint(self.api_call, _APIVersion.V3, "mock_request")

        response = await endpoint.execute()
        # Endpoint instantiates a default instance of the class
        self.assertEqual(MockResponse(RESTMethod.DELETE.value,
                                      "ok - api_delete called with "
                                      "() {'path_url': "
                                      # Concatenate the base url and the request.endpoint
                                      f"'{default_request.base_endpoint()}'"
                                      f", 'data': "
                                      f"{default_request.data()}"
                                      f", 'params': "
                                      f"{default_request.params()}"
                                      f", 'is_auth_required': "
                                      f"{default_request.is_auth_required()}"
                                      f", 'limit_id': "
                                      f"'{default_request.limit_id()}'"
                                      "}"), response)

    async def test_execute_get_method(self):
        await self.run_execute_test('api_get', method=RESTMethod.GET)

    async def test_execute_post_method(self):
        await self.run_execute_test('api_post', method=RESTMethod.POST)

    async def test_execute_delete_method(self):
        await self.run_execute_test('api_delete', method=RESTMethod.DELETE)

    async def test_execute_get_request_with_data(self):
        await self.run_execute_test('api_get', method=RESTMethod.GET, data={'test': 'data'})

    async def test_execute_get_request_with_params(self):
        await self.run_execute_test('api_get', method=RESTMethod.GET, params={'test': 'params'})

    async def test_execute_get_request_with_auth(self):
        await self.run_execute_test('api_get', method=RESTMethod.GET, is_auth_required=True)
        await self.run_execute_test('api_get', method=RESTMethod.GET, is_auth_required=False)

#    async def test_execute_get_request_with_limit_id(self):
#        await self.run_execute_test('api_get', method=RESTMethod.GET, limit_id="NewLimitID")

    @patch.object(MockRequest, 'add_rate_limit')
    @patch.object(request_data_types.CoinbaseAdvancedTradeRequest, 'find_class_by_name')
    @patch.object(response_data_types.CoinbaseAdvancedTradeResponse, 'find_class_by_name')
    async def test_invalid_method_exception(self, mock_get_response_class, mock_get_request_class,
                                            mock_request_add_rate_limit):
        mock_get_request_class.return_value = self.request_class
        mock_get_response_class.return_value = self.response_class

        with self.assertRaises(CoinbaseAdvancedTradeAPIEndpointException):
            endpoint_instance = CoinbaseAdvancedTradeAPIEndpoint(self.api_call, _APIVersion.V3, "mock_request", method="INVALID_METHOD")
            await endpoint_instance.execute()

    async def test_api_call_exception(self):
        class ExceptionAPICall:
            async def api_post(self, *args, **kwargs) -> Dict[str, Any]:
                raise Exception("API Post Error")

        with self.assertRaises(CoinbaseAdvancedTradeAPIEndpointException):
            endpoint_instance = CoinbaseAdvancedTradeAPIEndpoint(ExceptionAPICall(), _APIVersion.V3, "mock_request",
                                                                 method=RESTMethod.POST)
            await endpoint_instance.execute()

    @patch.object(request_data_types.CoinbaseAdvancedTradeRequest, 'find_class_by_name')
    @patch.object(response_data_types.CoinbaseAdvancedTradeResponse, 'find_class_by_name')
    def test_invalid_request_class(self, mock_get_response_class, mock_get_request_class):
        mock_get_request_class.return_value = None  # This would cause a type error when it tries to instantiate None
        mock_get_response_class.return_value = self.response_class

        with self.assertRaises(CoinbaseAdvancedTradeAPIEndpointException):
            CoinbaseAdvancedTradeAPIEndpoint(self.api_call, _APIVersion.V3, "mock_request")

    @patch.object(request_data_types.CoinbaseAdvancedTradeRequest, 'find_class_by_name')
    @patch.object(response_data_types.CoinbaseAdvancedTradeResponse, 'find_class_by_name')
    async def test_invalid_response_class(self, mock_get_response_class, mock_get_request_class):
        mock_get_request_class.return_value = self.request_class
        mock_get_response_class.return_value = None  # This would cause a type error when it tries to instantiate None

        with self.assertRaises(CoinbaseAdvancedTradeAPIEndpointException):
            endpoint = CoinbaseAdvancedTradeAPIEndpoint(self.api_call, _APIVersion.V3, "mock_request")
            await endpoint.execute()

    # def test_empty_endpoint(self):
    #     with self.assertRaises(CoinbaseAdvancedTradeAPIEndpointException):
    #         self.run_execute_test('api_get', method=RESTMethod.GET, endpoint="")
