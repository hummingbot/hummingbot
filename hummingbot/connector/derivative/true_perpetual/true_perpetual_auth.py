import hashlib
import hmac
import json
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlsplit

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class TruePerpetualAuth(AuthBase):
    """
    TRUE Bot API signing.

    Headers:  X-TRUE-KEY (tbk_...), X-TRUE-TS (unix ms), X-TRUE-SIGN
    Signature: hex(HMAC_SHA256(secret, ts + METHOD + path_with_query + raw_body))

    The server verifies the request exactly as it arrives, so the query string is folded
    into the URL before signing (aiohttp would otherwise append it itself) and the body is
    signed as the exact string that goes on the wire.
    """

    def __init__(self, api_key: str, api_secret: str, time_provider: TimeSynchronizer):
        self._api_key: str = api_key or ""
        self._api_secret: str = api_secret or ""
        self._time_provider: TimeSynchronizer = time_provider

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._api_secret)

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}

        url = request.url
        if request.params:
            query = urlencode(request.params, doseq=True)
            url = f"{url}{'&' if '?' in url else '?'}{query}"
            request.url = url
            request.params = None

        raw_body = self._raw_body(request)
        if raw_body is not None:
            request.data = raw_body
        body_for_signature = raw_body if raw_body is not None else ""

        timestamp = str(int(self._time_provider.time() * 1e3))
        method = request.method.value if isinstance(request.method, RESTMethod) else str(request.method)
        request.headers.update(self.sign_headers(
            timestamp=timestamp,
            method=method,
            path_with_query=self.path_with_query(url),
            raw_body=body_for_signature,
        ))
        if request.method != RESTMethod.GET:
            request.headers["Content-Type"] = "application/json"
        request.headers["Accept"] = "application/json"
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        # The websocket is authenticated on the upgrade with a short lived token from POST /ws-token.
        return request

    def sign_headers(self, timestamp: str, method: str, path_with_query: str, raw_body: str) -> Dict[str, str]:
        canonical = f"{timestamp}{method.upper()}{path_with_query}{raw_body}"
        signature = hmac.new(self._api_secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        return {
            "X-TRUE-KEY": self._api_key,
            "X-TRUE-TS": timestamp,
            "X-TRUE-SIGN": signature,
        }

    @staticmethod
    def path_with_query(url: str) -> str:
        parts = urlsplit(url)
        path = parts.path or "/"
        return f"{path}?{parts.query}" if parts.query else path

    @staticmethod
    def _raw_body(request: RESTRequest) -> Optional[str]:
        data: Any = request.data
        if data is None:
            return None
        if isinstance(data, bytes):
            return data.decode("utf-8")
        if isinstance(data, str):
            return data
        return json.dumps(data, separators=(",", ":"))
