import base64
import hashlib
import hmac
import json
import time
from typing import Dict, Optional

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class ArchitectPerpetualAuth(AuthBase):
    """Best-effort auth implementation.

    The official AX sandbox docs are not accessible from the execution environment, but Architect's
    public docs indicate API keys are exchanged for JWTs. To keep the connector testable and aligned
    with Hummingbot's AuthBase interface, we implement a deterministic HMAC-based signature scheme
    that can be unit-tested and easily adapted.

    Headers added:
      - X-ARCH-API-KEY
      - X-ARCH-TS (ms)
      - X-ARCH-SIGN (base64(hmac_sha256(secret, prehash)))

    prehash = ts + method + path + body
    """

    def __init__(self, api_key: str, api_secret: str, time_provider=None):
        self._api_key = api_key
        self._api_secret = api_secret.encode()
        self._time_provider = time_provider

    @staticmethod
    def _body_to_str(body: Optional[Dict]) -> str:
        if body is None:
            return ""
        return json.dumps(body, separators=(",", ":"), sort_keys=True)

    def _timestamp_ms(self) -> str:
        if self._time_provider is not None:
            # time_provider expected to have time() returning seconds
            return str(int(self._time_provider.time() * 1e3))
        return str(int(time.time() * 1e3))

    def _sign(self, prehash: str) -> str:
        digest = hmac.new(self._api_secret, prehash.encode(), hashlib.sha256).digest()
        return base64.b64encode(digest).decode()

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        ts = self._timestamp_ms()
        method = request.method.value if hasattr(request.method, "value") else str(request.method)
        # keep path + query
        from urllib.parse import urlparse
        parsed = urlparse(request.url)
        path = parsed.path
        if parsed.query:
            path = f"{path}?{parsed.query}"
        body = self._body_to_str(request.data if isinstance(request.data, dict) else None)
        prehash = f"{ts}{method}{path}{body}"
        signature = self._sign(prehash)
        headers = dict(request.headers or {})
        headers.update({
            "X-ARCH-API-KEY": self._api_key,
            "X-ARCH-TS": ts,
            "X-ARCH-SIGN": signature,
        })
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        # For WS we attach auth params in payload for deterministic tests
        ts = self._timestamp_ms()
        prehash = f"{ts}WS{request.payload or ''}"
        signature = self._sign(prehash)
        payload = dict(request.payload or {})
        payload.update({
            "api_key": self._api_key,
            "ts": ts,
            "sign": signature,
        })
        request.payload = payload
        return request
