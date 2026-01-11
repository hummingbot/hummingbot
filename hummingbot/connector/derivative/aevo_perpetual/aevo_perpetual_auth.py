import hashlib
import hmac
import time
from typing import Any, Dict
from urllib.parse import urlencode

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class AevoPerpetualAuth(AuthBase):
    def __init__(self, api_key: str, api_secret: str, time_provider: TimeSynchronizer):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._time_provider: TimeSynchronizer = time_provider

    def _generate_signature(self, timestamp: int, method: str, path: str, body: str = "") -> str:
        message = f"{timestamp}{method.upper()}{path}{body}"
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        timestamp = int(time.time() * 1000)
        path = request.url.split(".xyz")[-1] if ".xyz" in request.url else request.url

        body = ""
        if request.data:
            body = request.data if isinstance(request.data, str) else str(request.data)

        signature = self._generate_signature(
            timestamp=timestamp,
            method=request.method.value,
            path=path,
            body=body
        )

        headers = request.headers or {}
        headers.update({
            "AEVO-KEY": self._api_key,
            "AEVO-SECRET": self._api_secret,
            "AEVO-TIMESTAMP": str(timestamp),
            "AEVO-SIGNATURE": signature,
        })
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request

    def header_for_authentication(self) -> Dict[str, str]:
        return {
            "AEVO-KEY": self._api_key,
            "AEVO-SECRET": self._api_secret,
        }

    def get_ws_auth_payload(self) -> Dict[str, Any]:
        timestamp = int(time.time() * 1000)
        signature = self._generate_signature(timestamp, "GET", "/ws")
        return {
            "op": "auth",
            "data": {
                "key": self._api_key,
                "secret": self._api_secret,
            }
        }
