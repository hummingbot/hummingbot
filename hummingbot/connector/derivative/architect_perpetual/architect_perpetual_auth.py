import hashlib
import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class ArchitectPerpetualAuth(AuthBase):
    """
    Auth class for Architect Perpetual exchange.
    Uses Bearer token authentication.
    """

    def __init__(self, api_key: str, api_secret: str, time_provider: Optional[TimeSynchronizer] = None):
        self._api_key = api_key
        self._api_secret = api_secret
        self._time_provider = time_provider
        self._auth_token: Optional[str] = None
        self._token_expiry: float = 0

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def api_secret(self) -> str:
        return self._api_secret

    def _get_timestamp(self) -> int:
        if self._time_provider is not None:
            return int(self._time_provider.time() * 1000)
        return int(time.time() * 1000)

    def _generate_signature(self, timestamp: int, method: str, path: str, body: str = "") -> str:
        """Generate HMAC signature for request authentication."""
        message = f"{timestamp}{method.upper()}{path}{body}"
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Add authentication headers to REST request.
        Uses Bearer token in Authorization header.
        """
        timestamp = self._get_timestamp()
        
        headers = request.headers or {}
        headers["Authorization"] = f"Bearer {self._api_key}"
        headers["X-Timestamp"] = str(timestamp)
        headers["Content-Type"] = "application/json"
        
        # Generate signature if secret is provided
        if self._api_secret:
            method = request.method.value if hasattr(request.method, 'value') else str(request.method)
            path = request.url.split("?")[0] if request.url else ""
            body = request.data if request.data else ""
            signature = self._generate_signature(timestamp, method, path, body)
            headers["X-Signature"] = signature
        
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Add authentication to WebSocket request.
        """
        timestamp = self._get_timestamp()
        
        payload = request.payload or {}
        payload["api_key"] = self._api_key
        payload["timestamp"] = timestamp
        
        if self._api_secret:
            signature = self._generate_signature(timestamp, "SUBSCRIBE", "", "")
            payload["signature"] = signature
        
        request.payload = payload
        return request
