import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Mapping, Optional

import aiohttp
import ujson

if TYPE_CHECKING:
    from hummingbot.core.web_assistant.connections.ws_connection import WSConnection


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
    endpoint_url: Optional[str] = None
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
    _text: str
    _json: Any

    # We could also use this, but an await is needed,
    # so backward compatibility is broken anyway
    # def __await__(self, aiohttp_response: aiohttp.ClientResponse):
    #    return self.read(aiohttp_response).__await__()

    async def read(self, aiohttp_response: aiohttp.ClientResponse):
        self._json = await aiohttp_response.json()
        self._text = await aiohttp_response.text()
        self.method = RESTMethod[aiohttp_response.method.upper()]
        self.status = int(aiohttp_response.status)
        self.url = str(aiohttp_response.url)
        self.headers = aiohttp_response.headers
        return self

    async def json(self) -> Any:
        await asyncio.sleep(0)
        return self._json

    async def text(self) -> str:
        await asyncio.sleep(0)
        return self._text


class WSRequest(ABC):
    @abstractmethod
    async def send_with_connection(self, connection: 'WSConnection'):
        return NotImplemented


@dataclass
class WSJSONRequest(WSRequest):
    payload: Mapping[str, Any]
    throttler_limit_id: Optional[str] = None
    is_auth_required: bool = False

    async def send_with_connection(self, connection: 'WSConnection'):
        await connection._send_json(payload=self.payload)


@dataclass
class WSPlainTextRequest(WSRequest):
    payload: str
    throttler_limit_id: Optional[str] = None
    is_auth_required: bool = False

    async def send_with_connection(self, connection: 'WSConnection'):
        await connection._send_plain_text(payload=self.payload)


@dataclass
class WSResponse:
    data: Any
