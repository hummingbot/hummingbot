from typing import Any, Dict, Type

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_request_types import (
    CoinbaseAdvancedTradeRequestError,
    CoinbaseAdvancedTradeRequestType,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_response_types import (
    CoinbaseAdvancedTradeErrorResponse,
    CoinbaseAdvancedTradeResponse,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_exchange_protocols import (
    CoinbaseAdvancedTradeAPICallsMixinProtocol,
)
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class CoinbaseAdvancedTradeAPIEndpointError(Exception):
    pass


class CoinbaseAdvancedTradeAPIEndpoint:
    """
    Base class for Coinbase Advanced Trade API endpoints.

    :param request: The request object for the API endpoint.
    """
    endpoint_base: str = "api/v3/brokerage"

    def __init__(self,
                 api_call: CoinbaseAdvancedTradeAPICallsMixinProtocol,
                 request: str,
                 **kwargs,
                 ):
        self.api_call: CoinbaseAdvancedTradeAPICallsMixinProtocol = api_call
        self.request_class: Type[
            CoinbaseAdvancedTradeRequestType] = CoinbaseAdvancedTradeRequestType.find_class_by_name(request)

        if self.request_class is None:
            raise CoinbaseAdvancedTradeAPIEndpointError(f"No Request endpoint found with name {request}")

        try:
            self.request: CoinbaseAdvancedTradeRequestType = self.request_class(**kwargs)
        except TypeError as e:
            raise CoinbaseAdvancedTradeAPIEndpointError(f"Error creating request object for {request}: {e}")

        # Add the rate limit for the endpoint in the global RATE_LIMIT registry
        self.request.add_rate_limit(self.endpoint_base)

        # Lookup the response class in the endpoint map
        try:
            response_class: Type[CoinbaseAdvancedTradeResponse] = CoinbaseAdvancedTradeResponse.find_class_by_name(
                request)
        except CoinbaseAdvancedTradeRequestError as e:
            raise CoinbaseAdvancedTradeRequestError(f"Error creating request object for {request}: {e}")

        if response_class is None:
            raise CoinbaseAdvancedTradeAPIEndpointError(
                f"No endpoint found with shortname {request} (request class {self.request.__class__.__name__})")

        self.response_class: Type[CoinbaseAdvancedTradeResponse] = response_class

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
        return self.request.limit_id

    async def execute(self) -> CoinbaseAdvancedTradeResponse:
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
            raise CoinbaseAdvancedTradeAPIEndpointError(f"Unsupported method {self.method}")

        try:
            response_instance: CoinbaseAdvancedTradeResponse = self.response_class(**result)
            return response_instance
        except TypeError as e:
            try:
                CoinbaseAdvancedTradeErrorResponse(**result)
            except Exception:
                raise CoinbaseAdvancedTradeAPIEndpointError(f"Unregistered Error for {self.request.endpoint}: {e}")
