import hashlib
import hmac
import json
from typing import Any, Dict, Mapping
from urllib.parse import urlencode, urlsplit

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class XtAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer, recv_window_ms: int = 5000):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider
        self.recv_window_ms = recv_window_ms

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers: Dict[str, str] = dict(request.headers or {})
        if request.params:
            request.params = dict(sorted(request.params.items()))
        body = compact_json_payload(request.data)
        if body:
            request.data = body
            headers["Content-Type"] = "application/json"
        headers.update(build_auth_headers(
            api_key=self.api_key,
            secret_key=self.secret_key,
            timestamp_ms=int(self.time_provider.time() * 1e3),
            method=request.method.value,
            path_url=urlsplit(request.url).path,
            params=request.params,
            body=request.data,
            recv_window_ms=self.recv_window_ms,
        ))
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        # Private subscriptions use an authenticated REST token instead of WS signing.
        return request


XT_AUTH_ALGORITHM = "HmacSHA256"
XT_AUTH_HEADER_KEYS = (
    "validate-algorithms",
    "validate-appkey",
    "validate-recvwindow",
    "validate-timestamp",
)


def compact_json_payload(payload: Any) -> str:
    if payload is None or payload == "":
        return ""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return payload
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def canonical_query_string(params: Mapping[str, Any] | None) -> str:
    if not params:
        return ""
    return urlencode(sorted(params.items()), doseq=True)


def build_signature_payload(
    auth_headers: Mapping[str, Any],
    method: str,
    path_url: str,
    params: Mapping[str, Any] | None = None,
    body: Any = None,
) -> str:
    header_payload = "&".join(
        f"{key}={auth_headers[key]}" for key in sorted(XT_AUTH_HEADER_KEYS)
    )
    request_payload = f"#{method.upper()}#{path_url}"
    query_string = canonical_query_string(params)
    body_payload = compact_json_payload(body)
    if query_string:
        request_payload = f"{request_payload}#{query_string}"
    if body_payload:
        request_payload = f"{request_payload}#{body_payload}"
    return f"{header_payload}{request_payload}"


def generate_signature(secret_key: str, payload: str) -> str:
    return hmac.new(
        secret_key.encode("utf-8"),
        msg=payload.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def build_auth_headers(
    api_key: str,
    secret_key: str,
    timestamp_ms: int,
    method: str,
    path_url: str,
    params: Mapping[str, Any] | None = None,
    body: Any = None,
    recv_window_ms: int = 5000,
) -> dict[str, str]:
    headers = {
        "validate-algorithms": XT_AUTH_ALGORITHM,
        "validate-appkey": api_key,
        "validate-recvwindow": str(recv_window_ms),
        "validate-timestamp": str(timestamp_ms),
    }
    payload = build_signature_payload(
        auth_headers=headers,
        method=method,
        path_url=path_url,
        params=params,
        body=body,
    )
    headers["validate-signature"] = generate_signature(
        secret_key=secret_key,
        payload=payload,
    )
    return headers
