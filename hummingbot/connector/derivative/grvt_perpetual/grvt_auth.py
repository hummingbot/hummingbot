import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional, Union
from urllib.parse import urlsplit

from hummingbot.connector.derivative.grvt_perpetual import grvt_constants as CONSTANTS
from hummingbot.connector.derivative.grvt_perpetual.grvt_eip712 import (
    build_action_typed_data,
    sign_typed_action,
)
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest, WSRequest


class GrvtAuth(AuthBase):
    """
    Authentication helper for GRVT Perpetual.

    Current behavior:
    1) Adds HMAC headers for authenticated REST requests.
    2) Injects optional EIP-712 signatures into order-management POST bodies.
    3) Authenticates WS requests with API key + timestamp + signature (+ optional session token).
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        ethereum_private_key: Optional[str] = None,
        account_address: Optional[str] = None,
        chain_id: int = 1,
        verifying_contract: str = "0x0000000000000000000000000000000000000000",
        time_provider: Optional[Any] = None,
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._ethereum_private_key = ethereum_private_key
        self._account_address = account_address
        self._chain_id = chain_id
        self._verifying_contract = verifying_contract
        self._time_provider = time_provider
        self._session_token: Optional[str] = None

    @property
    def session_token(self) -> Optional[str]:
        return self._session_token

    def set_session_token(self, token: Optional[str]) -> None:
        self._session_token = token

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if not request.is_auth_required:
            return request

        timestamp = self._timestamp_ms()
        method = request.method.value.upper()
        path = self._path_from_url(request.url or "")

        body_payload = self._deserialize_payload(request.data)
        if request.method == RESTMethod.POST and isinstance(body_payload, dict):
            body_payload = self._decorate_post_payload(payload=body_payload, timestamp_ms=timestamp)
            request.data = json.dumps(body_payload, separators=(",", ":"), ensure_ascii=False)
            body = request.data
        else:
            body = self._serialize_payload(request.data)

        signature = self._hmac_signature(timestamp=timestamp, method=method, path=path, body=body)
        headers = dict(request.headers or {})
        headers.update(self._auth_headers(timestamp=timestamp, signature=signature))
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        if not isinstance(request, WSJSONRequest):
            return request

        timestamp = self._timestamp_ms()
        signature = self._hmac_signature(timestamp=timestamp, method="GET", path="/ws", body="")
        payload = dict(request.payload or {})
        payload.update(
            {
                "op": "auth",
                "args": {
                    "apiKey": self._api_key,
                    "timestamp": timestamp,
                    "signature": signature,
                },
            }
        )
        if self._session_token:
            payload["args"]["token"] = self._session_token
        request.payload = payload
        return request

    def _decorate_post_payload(self, payload: Dict[str, Any], timestamp_ms: str) -> Dict[str, Any]:
        request_type = str(payload.get("type", "")).strip().lower()
        if request_type not in {"order", "cancel", "updateleverage"}:
            return payload
        if not self._ethereum_private_key or not self._account_address:
            return payload

        nonce = int(timestamp_ms)
        typed_data = build_action_typed_data(
            account_address=self._account_address,
            action_payload=payload,
            nonce=nonce,
            chain_id=self._chain_id,
            verifying_contract=self._verifying_contract,
        )
        signature = sign_typed_action(private_key=self._ethereum_private_key, typed_data=typed_data)
        signed_payload = dict(payload)
        signed_payload["nonce"] = nonce
        signed_payload["signature"] = signature
        signed_payload["account"] = self._account_address
        return signed_payload

    def _auth_headers(self, timestamp: str, signature: str) -> Dict[str, str]:
        headers = {
            CONSTANTS.API_KEY_HEADER: self._api_key,
            CONSTANTS.TIMESTAMP_HEADER: timestamp,
            CONSTANTS.SIGNATURE_HEADER: signature,
        }
        if self._session_token:
            headers[CONSTANTS.SESSION_TOKEN_HEADER] = self._session_token
            headers["Authorization"] = f"Bearer {self._session_token}"
        return headers

    def _hmac_signature(self, timestamp: str, method: str, path: str, body: str) -> str:
        payload = f"{timestamp}{method}{path}{body}"
        return hmac.new(
            self._api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _path_from_url(self, url: str) -> str:
        parts = urlsplit(url)
        path = parts.path or "/"
        if parts.query:
            return f"{path}?{parts.query}"
        return path

    def _timestamp_ms(self) -> str:
        return str(int(self._time() * 1e3))

    def _time(self) -> float:
        if self._time_provider is None:
            return time.time()
        if callable(self._time_provider):
            return float(self._time_provider())
        if hasattr(self._time_provider, "time"):
            return float(self._time_provider.time())
        return time.time()

    def _serialize_payload(self, payload: Union[str, bytes, Dict[str, Any], None]) -> str:
        if payload is None:
            return ""
        if isinstance(payload, bytes):
            return payload.decode("utf-8")
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict):
            return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
        return str(payload)

    def _deserialize_payload(self, payload: Union[str, bytes, Dict[str, Any], None]) -> Union[Dict[str, Any], Any]:
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        if isinstance(payload, str):
            text = payload.strip()
            if not text:
                return {}
            try:
                return json.loads(text)
            except Exception:
                return {"raw": payload}
        return payload
