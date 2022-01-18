from abc import abstractmethod, ABC
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional

import aiohttp
import ujson


class RESTMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"

    def __str__(self):
        obj_str = repr(self)
        return obj_str

    def __repr__(self):
        return self.value


@dataclass
class RESTRequest:
    method: RESTMethod
    url: Optional[str] = None
    params: Optional[Mapping[str, str]] = None
    data: Any = None
    headers: Optional[Mapping[str, str]] = None
    is_auth_required: bool = False
    throttler_limit_id: Optional[str] = None


@dataclass
class EndpointRESTRequest(RESTRequest, ABC):
    """This request class enable the user to provide either a complete URL or simply an endpoint.

    The endpoint is concatenated with the return value of `base_url`. It can handle endpoints supplied both as
    `"endpoint"` and `"/endpoint"`. It also provides the necessary checks to ensure a valid URL can be constructed.
    """

    endpoint: Optional[str] = None

    def __post_init__(self):
        self._ensure_url()
        self._ensure_params()
        self._ensure_data()

    @property
    @abstractmethod
    def base_url(self) -> str:
        ...

    def _ensure_url(self):
        if self.url is None and self.endpoint is None:
            raise ValueError("Either the full url or the endpoint must be specified.")
        if self.url is None:
            if self.endpoint.startswith("/"):
                self.url = f"{self.base_url}{self.endpoint}"
            else:
                self.url = f"{self.base_url}/{self.endpoint}"

    def _ensure_params(self):
        if self.method == RESTMethod.POST:
            if self.params is not None:
                raise ValueError("POST requests should not use `params`. Use `data` instead.")

    def _ensure_data(self):
        if self.method == RESTMethod.POST:
            if self.data is not None:
                self.data = ujson.dumps(self.data)
        elif self.data is not None:
            raise ValueError(
                "The `data` field should be used only for POST requests. Use `params` instead."
            )


@dataclass(init=False)
class RESTResponse:
    url: str
    method: RESTMethod
    status: int
    headers: Optional[Mapping[str, str]]

    def __init__(self, aiohttp_response: aiohttp.ClientResponse):
        self._aiohttp_response = aiohttp_response

    @property
    def url(self) -> str:
        url_str = str(self._aiohttp_response.url)
        return url_str

    @property
    def method(self) -> RESTMethod:
        method_ = RESTMethod[self._aiohttp_response.method.upper()]
        return method_

    @property
    def status(self) -> int:
        status_ = int(self._aiohttp_response.status)
        return status_

    @property
    def headers(self) -> Optional[Mapping[str, str]]:
        headers_ = self._aiohttp_response.headers
        return headers_

    async def json(self) -> Any:
        json_ = await self._aiohttp_response.json()
        return json_

    async def text(self) -> str:
        text_ = await self._aiohttp_response.text()
        return text_


@dataclass
class WSRequest:
    payload: Mapping[str, Any]
    throttler_limit_id: Optional[str] = None
    is_auth_required: bool = False


@dataclass
class WSResponse:
    data: Any
