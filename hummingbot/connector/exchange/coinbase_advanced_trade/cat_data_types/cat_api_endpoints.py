from enum import auto
from typing import Any, Dict, Protocol, Tuple, Type

from pydantic.dataclasses import TypeVar

from hummingbot.core.web_assistant.connections.data_types import RESTMethod

from ..cat_exchange_mixins.cat_exchange_protocols import CoinbaseAdvancedTradeAPICallsMixinProtocol as _APICallsPtl
from .cat_api_v2_request_types import (  # CoinbaseAdvancedTradeV2RequestException as _V2RequestException,
    CoinbaseAdvancedTradeV2Request as _V2Request,
)
from .cat_api_v2_response_types import CoinbaseAdvancedTradeTimeResponse as _V2Response
from .cat_api_v3_enums import StrEnum
from .cat_api_v3_request_types import (
    CoinbaseAdvancedTradeRequest as _V3Request,
    CoinbaseAdvancedTradeRequestException as _V3RequestException,
)
from .cat_api_v3_response_types import (
    CoinbaseAdvancedTradeErrorResponse as _ErrorV3Response,
    CoinbaseAdvancedTradeResponse as _V3Response,
)
from .cat_protocols import CoinbaseAdvancedTradeAPIRequestProtocol


class CoinbaseAdvancedTradeAPIEndpointException(Exception):
    pass


class CoinbaseAdvancedTradeAPIVersionEnum(StrEnum):
    V2 = auto()
    V3 = auto()


class _ClassFinderPtl(Protocol):
    def find_class_by_name(self, name: str) -> Type:
        ...


_API_VERSION_TO_CLASSES: Dict[
    CoinbaseAdvancedTradeAPIVersionEnum,
    Tuple[_ClassFinderPtl, _ClassFinderPtl]
] = {
    CoinbaseAdvancedTradeAPIVersionEnum.V2: (_V2Request, _V2Response),
    CoinbaseAdvancedTradeAPIVersionEnum.V3: (_V3Request, _V3Response),
}

T = TypeVar("T", "_V2Response", "_V3Response")


class CoinbaseAdvancedTradeAPIEndpoint:
    """
    Base class for Coinbase Advanced Trade API endpoints. This class provides most ot the attributes and methods
    of the Request, prepends the rate limit ID, tunes the endpoint url.
    It facilitates making the API call, and returning the response by matching the Response class to the Request class
    together
    """

    def __init__(self,
                 api_call: _APICallsPtl,
                 api_version: CoinbaseAdvancedTradeAPIVersionEnum,
                 request_name: str,
                 **kwargs,
                 ):
        self.api_call: _APICallsPtl = api_call

        request_type: _ClassFinderPtl = _API_VERSION_TO_CLASSES[api_version][0]
        response_type: _ClassFinderPtl = _API_VERSION_TO_CLASSES[api_version][1]

        self.request_class: Type[request_type] = request_type.find_class_by_name(request_name)

        if self.request_class is None:
            raise CoinbaseAdvancedTradeAPIEndpointException(f"No Request endpoint found with name {request_name}")

        try:
            self.request: _V3Request = self.request_class(**kwargs)
        except TypeError as e:
            raise CoinbaseAdvancedTradeAPIEndpointException(f"Error creating request object for {request_name}: {e}")

        try:
            response_class: Type[response_type] = response_type.find_class_by_name(request_name)
        except _V3RequestException as e:
            raise CoinbaseAdvancedTradeAPIEndpointException(f"Error creating request object for {request_name}: {e}")

        if response_class is None:
            raise CoinbaseAdvancedTradeAPIEndpointException(
                f"No endpoint found with shortname {request_name} (request class {self.request.__class__.__name__})")

        self.response_class: Type[response_type] = response_class

    async def execute(self) -> T:
        """
        Executes the API request and returns the response.

        :return: The API response.
        """
        request: CoinbaseAdvancedTradeAPIRequestProtocol = self.request

        method: RESTMethod = request.method()
        path_url: str = request.base_endpoint()
        data: Dict[str, Any] = request.data()
        params: Dict[str, Any] = request.params()
        is_auth_required: bool = request.is_auth_required()
        limit_id: str = request.limit_id()

        if method == RESTMethod.GET:
            result: Dict[str, Any] = await self.api_call.api_get(
                path_url=path_url,
                data=data,
                params=params,
                is_auth_required=is_auth_required,
                limit_id=limit_id,
            )
        elif method == RESTMethod.POST:
            result: Dict[str, Any] = await self.api_call.api_post(
                path_url=path_url,
                data=data,
                params=params,
                is_auth_required=is_auth_required,
                limit_id=limit_id,
            )
        elif method == RESTMethod.DELETE:
            result: Dict[str, Any] = await self.api_call.api_delete(
                path_url=path_url,
                data=data,
                params=params,
                is_auth_required=is_auth_required,
                limit_id=limit_id,
            )
        else:
            raise CoinbaseAdvancedTradeAPIEndpointException(f"Unsupported method {method}")

        try:
            response_instance: T = self.response_class(**result)
            return response_instance
        except TypeError as e:
            try:
                _ErrorV3Response(**result)
            except Exception:
                raise CoinbaseAdvancedTradeAPIEndpointException(
                    f"Unregistered Error for {request.base_endpoint()}: {e}")
