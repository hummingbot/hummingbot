import hashlib
import hmac
import json
from collections import OrderedDict
from decimal import Decimal
from typing import Any, Dict
from urllib.parse import urlparse

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class CryptocomAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        payload = json.loads(request.data) if request.data else {}
        signed = self._sign_payload(payload=payload, request_url=request.url)
        request.data = json.dumps(signed)

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication())
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request

    def get_ws_auth_payload(self) -> Dict[str, Any]:
        payload = {
            "id": self._nonce(),
            "method": "public/auth",
            "params": {},
        }
        return self._sign_payload(payload=payload)

    def header_for_authentication(self) -> Dict[str, str]:
        return {"Content-Type": "application/json"}

    def _nonce(self) -> int:
        return int(self.time_provider.time() * 1e3)

    def _sign_payload(self, payload: Dict[str, Any], request_url: str = "") -> Dict[str, Any]:
        request_data = OrderedDict(payload)

        method = request_data.get("method")
        if not method and request_url:
            parsed_path = urlparse(request_url).path
            method = parsed_path.lstrip("/")
            request_data["method"] = method

        request_id = int(request_data.get("id") or self._nonce())
        request_data["id"] = request_id

        nonce = int(request_data.get("nonce") or self._nonce())
        request_data["nonce"] = nonce

        params = request_data.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        request_data["params"] = params
        request_data["api_key"] = self.api_key

        payload_to_sign = f"{method}{request_id}{self.api_key}{self._params_to_str(params)}{nonce}"
        request_data["sig"] = hmac.new(
            self.secret_key.encode("utf8"),
            payload_to_sign.encode("utf8"),
            hashlib.sha256,
        ).hexdigest()

        return request_data

    def _params_to_str(self, params: Dict[str, Any]) -> str:
        ordered = OrderedDict(sorted(params.items(), key=lambda item: item[0]))
        return "".join(self._value_to_str(key) + self._value_to_str(value) for key, value in ordered.items())

    def _value_to_str(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, float):
            return format(Decimal(str(value)).normalize(), "f")
        if isinstance(value, dict):
            return "".join(
                self._value_to_str(k) + self._value_to_str(v)
                for k, v in sorted(value.items(), key=lambda item: item[0])
            )
        if isinstance(value, list):
            return "".join(self._value_to_str(v) for v in value)
        return str(value)
