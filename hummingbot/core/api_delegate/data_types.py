import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional


class RESTMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"

    def __str__(self):
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
class RESTResponse:
    url: str
    method: RESTMethod
    status: int
    body: bytes
    headers: Optional[Mapping[str, str]] = None

    def json(self) -> Any:
        body_json = json.loads(self.body)
        return body_json

    def text(self) -> str:
        body_text = self.body.decode()
        return body_text


@dataclass
class WSRequest:
    payload: Mapping[str, Any]
    throttler_limit_id: Optional[str] = None


@dataclass
class WSResponse:
    data: Any
