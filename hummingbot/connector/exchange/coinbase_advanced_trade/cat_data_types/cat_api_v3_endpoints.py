from typing import Any, Dict, Type

from pydantic.dataclasses import TypeVar

from hummingbot.core.web_assistant.connections.data_types import RESTMethod

from ..cat_exchange_mixins.cat_exchange_protocols import CoinbaseAdvancedTradeAPICallsMixinProtocol as _APICallsPtl
from .cat_api_v3_request_types import (
    CoinbaseAdvancedTradeRequest as _Request,
    CoinbaseAdvancedTradeRequestException as _RequestException,
)
from .cat_api_v3_response_types import (
    CoinbaseAdvancedTradeErrorResponse as _ErrorResponse,
    CoinbaseAdvancedTradeResponse as _Response,
)


class CoinbaseAdvancedTradeAPIEndpointException(Exception):
    pass


T = TypeVar("T", bound="_Response")


class CoinbaseAdvancedTradeAPIEndpoint:
    """
    Base class for Coinbase Advanced Trade API endpoints. This class provides most ot the attributes and methods
    of the Request, prepends the rate limit ID, tunes the endpoint url.
    It facilitates making the API call, and returning the response by matching the Response class to the Request class
    together
    """
    endpoint_base: str = "api/v3/brokerage"

    def __init__(self,
                 api_call: _APICallsPtl,
                 request_name: str,
                 **kwargs,
                 ):
        self.api_call: _APICallsPtl = api_call
        self.request_class: Type[_Request] = _Request.find_class_by_name(request_name)

        if self.request_class is None:
            raise CoinbaseAdvancedTradeAPIEndpointException(f"No Request endpoint found with name {request_name}")

        try:
            self.request: _Request = self.request_class(**kwargs)
        except TypeError as e:
            raise CoinbaseAdvancedTradeAPIEndpointException(f"Error creating request object for {request_name}: {e}")

        try:
            response_class: Type[_Response] = _Response.find_class_by_name(request_name)
        except _RequestException as e:
            raise CoinbaseAdvancedTradeAPIEndpointException(f"Error creating request object for {request_name}: {e}")

        if response_class is None:
            raise CoinbaseAdvancedTradeAPIEndpointException(
                f"No endpoint found with shortname {request_name} (request class {self.request.__class__.__name__})")

        self.response_class: Type[_Response] = response_class

    @property
    def endpoint(self) -> str:
        """
        Get the API endpoint.
        :return: The API endpoint.
        """
        return f"{self.endpoint_base}/{self.request.endpoint}"

    @property
    def method(self) -> RESTMethod:
        """
        Get the request method.
        :return: The request method.
        """
        return self.request.method

    def data(self) -> Dict[str, Any]:
        """
        Get the request data for the API endpoint.
        :return: Dictionary containing the request data.
        """
        return self.request.data()

    def params(self) -> Dict[str, Any]:
        """
        Get the request parameters for the API endpoint.
        :return: Dictionary containing the request parameters.
        """
        return self.request.params()

    def is_auth_required(self) -> bool:
        """
        Get the request parameters for the API endpoint.
        :return: Dictionary containing the request parameters.
        """
        return self.request.is_auth_required()

    @property
    def limit_id(self) -> str:
        """
        Get the request parameters for the API endpoint.
        :return: Dictionary containing the request parameters.
        """
        return self.request.limit_id()

    async def execute(self) -> T:
        """
        Executes the API request and returns the response.

        :return: The API response.
        """
        path_url: str = self.endpoint
        data: Dict[str, Any] = self.data()
        params: Dict[str, Any] = self.params()
        is_auth_required: bool = self.is_auth_required()
        limit_id: str = self.limit_id

        if self.method == RESTMethod.GET:
            result: Dict[str, Any] = await self.api_call.api_get(
                path_url=path_url,
                data=data,
                params=params,
                is_auth_required=is_auth_required,
                limit_id=limit_id,
            )
        elif self.method == RESTMethod.POST:
            result: Dict[str, Any] = await self.api_call.api_post(
                path_url=path_url,
                data=data,
                params=params,
                is_auth_required=is_auth_required,
                limit_id=limit_id,
            )
        elif self.method == RESTMethod.DELETE:
            result: Dict[str, Any] = await self.api_call.api_delete(
                path_url=path_url,
                data=data,
                params=params,
                is_auth_required=is_auth_required,
                limit_id=limit_id,
            )
        else:
            raise CoinbaseAdvancedTradeAPIEndpointException(f"Unsupported method {self.method}")

        try:
            response_instance: T = self.response_class(**result)
            return response_instance
        except TypeError as e:
            try:
                _ErrorResponse(**result)
            except Exception:
                raise CoinbaseAdvancedTradeAPIEndpointException(f"Unregistered Error for {self.request.endpoint}: {e}")
