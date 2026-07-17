import asyncio
import base64
import hashlib
import hmac
import json
import threading
import time
from typing import Any, Dict, Optional

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


NONCE_DRIFT_RESET_MS = 15_000


class GeminiAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: Optional[TimeSynchronizer] = None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider
        self._last_nonce: int = 0
        self._nonce_lock = threading.Lock()
        # Gemini compares nonces per API-key session. The exchange serializes every
        # authenticated REST dispatch and websocket handshake with this lock so nonce
        # generation order cannot diverge from network-send order across transports.
        self._request_lock = asyncio.Lock()

    @property
    def request_lock(self) -> asyncio.Lock:
        return self._request_lock

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Gemini REST API authentication uses payload-based signing.
        The payload is a base64-encoded JSON object containing the request path, nonce, and parameters.
        """
        nonce = self._get_nonce()

        # Build the payload from existing request data
        payload_dict: Dict[str, Any] = {}
        if request.data:
            if isinstance(request.data, str):
                payload_dict = json.loads(request.data)
            elif isinstance(request.data, dict):
                payload_dict = dict(request.data)

        payload_dict["nonce"] = nonce

        # The "request" field must be set by the caller in request.data
        # e.g., {"request": "/v1/order/new", "symbol": "btcusd", ...}

        payload_json = json.dumps(payload_dict)
        payload_b64 = base64.b64encode(payload_json.encode("utf-8"))

        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            payload_b64,
            hashlib.sha384
        ).hexdigest()

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers["Content-Type"] = "text/plain"
        headers["Content-Length"] = "0"
        headers["X-GEMINI-APIKEY"] = self.api_key
        headers["X-GEMINI-PAYLOAD"] = payload_b64.decode("utf-8")
        headers["X-GEMINI-SIGNATURE"] = signature
        headers["Cache-Control"] = "no-cache"

        request.headers = headers
        # Gemini expects an empty body; the payload is in the header
        request.data = None

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Fast API WebSocket authentication via handshake headers.
        """
        nonce = self._format_nonce(self._get_nonce())
        payload_b64 = base64.b64encode(nonce.encode("utf-8")).decode("utf-8")

        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha384
        ).hexdigest()

        headers = request.headers or {}
        headers["X-GEMINI-APIKEY"] = self.api_key
        headers["X-GEMINI-NONCE"] = nonce
        headers["X-GEMINI-PAYLOAD"] = payload_b64
        headers["X-GEMINI-SIGNATURE"] = signature
        request.headers = headers

        return request

    def get_ws_auth_headers(self) -> Dict[str, str]:
        """
        Generate authentication headers for WebSocket connection.
        Used when connecting via raw websocket libraries that need headers at connect time.
        """
        nonce = self._format_nonce(self._get_nonce())
        payload_b64 = base64.b64encode(nonce.encode("utf-8")).decode("utf-8")

        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha384
        ).hexdigest()

        return {
            "X-GEMINI-APIKEY": self.api_key,
            "X-GEMINI-NONCE": nonce,
            "X-GEMINI-PAYLOAD": payload_b64,
            "X-GEMINI-SIGNATURE": signature,
        }

    @staticmethod
    def _format_nonce(nonce: int) -> str:
        return str(nonce)

    def _get_nonce(self) -> int:
        """Return a strictly increasing time-based nonce expressed in epoch milliseconds.

        Gemini's authenticated websocket requires a time-based account key, and the
        same key is used for REST fallback. The synchronizer feeds this timestamp,
        so InvalidNonce time resyncs can move the base clock down; the drift reset
        prevents a previously poisoned high nonce from pinning retries out of range.
        """
        timestamp_ms = int((self.time_provider.time() if self.time_provider is not None else time.time()) * 1e3)
        with self._nonce_lock:
            if self._last_nonce > timestamp_ms + NONCE_DRIFT_RESET_MS:
                self._last_nonce = timestamp_ms - 1
            nonce = max(timestamp_ms, self._last_nonce + 1)
            self._last_nonce = nonce
            return nonce
