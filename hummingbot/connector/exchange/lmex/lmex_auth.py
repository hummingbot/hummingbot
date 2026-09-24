import hashlib
import hmac
import json
from typing import Dict, Optional
from urllib.parse import urlparse

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class LmexAuth(AuthBase):
    """
    Authentication for LMEX REST API.
    https://lmex.io/apidocs/spot/#authentication

    Signature = HMAC-SHA384(secret, path + nonce + body)

    Rules:
    - path  : URL path only — query parameters are NOT included in the signature
    - nonce : epoch milliseconds as a string
    - body  : JSON string for POST/PUT/DELETE with a body, empty string for GET
    Headers sent: request-api, request-nonce, request-sign
    """

    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self._api_key = api_key
        self._secret_key = secret_key
        self._time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        nonce = str(int(self._time_provider.time() * 1e3))
        path = urlparse(request.url).path

        body_str = ""
        if request.data is not None:
            body_str = request.data if isinstance(request.data, str) else json.dumps(request.data)

        signature = self._generate_signature(path, nonce, body_str)

        headers: Dict[str, str] = {} if request.headers is None else dict(request.headers)
        headers.update(
            {
                "request-api": self._api_key,
                "request-nonce": nonce,
                "request-sign": signature,
                "Content-Type": "application/json",
            }
        )
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        LMEX WebSocket authentication.
        Inject auth args into the payload so the WS auth frame can be sent after connect.
        The path used for WS auth signature follows the BTSE-family pattern.
        """
        nonce = str(int(self._time_provider.time() * 1e3))
        signature = self._generate_signature("/api/v3.2/user/verifyUser", nonce, "")
        request.payload["args"] = [self._api_key, nonce, signature]
        return request

    def _generate_signature(self, path: str, nonce: str, body: str) -> str:
        message = path + nonce + body
        return hmac.new(
            self._secret_key.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha384,
        ).hexdigest()

    @property
    def api_key(self) -> str:
        return self._api_key
