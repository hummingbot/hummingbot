import hashlib
import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class LmexPerpetualAuth(AuthBase):
    """
    Authentication for LMEX Futures REST API.

    Signature scheme (identical to LMEX Spot):
        HMAC-SHA384(secret_key, path + nonce + body)

    Headers required:
        request-api   : API key
        request-nonce : millisecond timestamp string
        request-sign  : hex HMAC-SHA384 digest
    """

    def __init__(self, api_key: str, secret_key: str):
        self._api_key = api_key
        self._secret_key = secret_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers: Dict[str, Any] = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self._generate_auth_headers(request))
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        # LMEX Futures uses REST-only authentication; no WS auth required.
        return request

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_auth_headers(self, request: RESTRequest) -> Dict[str, str]:
        nonce = str(int(time.time() * 1000))
        path = urlparse(request.url).path

        body = ""
        if request.data is not None:
            import json
            if isinstance(request.data, str):
                body = request.data
            else:
                body = json.dumps(request.data, separators=(",", ":"))

        raw_signature = path + nonce + body
        signature = hmac.new(
            self._secret_key.encode("utf-8"),
            raw_signature.encode("utf-8"),
            hashlib.sha384,
        ).hexdigest()

        return {
            "request-api": self._api_key,
            "request-nonce": nonce,
            "request-sign": signature,
            "Content-Type": "application/json",
        }

    @property
    def api_key(self) -> str:
        return self._api_key
