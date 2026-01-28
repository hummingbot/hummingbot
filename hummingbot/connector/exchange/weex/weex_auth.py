# hummingbot/connector/exchange/weex/weex_auth.py

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.connector.exchange.weex import weex_constants as CONSTANTS


@dataclass
class WeexAuth(AuthBase):
    api_key: str
    secret_key: str
    passphrase: Optional[str] = None
    time_provider: Optional[Any] = None  # Hummingbot will pass this in

    def _now_ms(self) -> str:
        # Use the provided time source if available; fall back to local time.
        if self.time_provider is not None:
            # Different builds expose different methods; try common ones safely.
            for attr in ("time", "time_s", "current_timestamp", "get_current_timestamp"):
                if hasattr(self.time_provider, attr):
                    v = getattr(self.time_provider, attr)
                    ts = v() if callable(v) else v
                    # if seconds, convert; if ms already, keep
                    if ts > 1e12:
                        return str(int(ts))
                    return str(int(ts * 1000))
        import time
        return str(int(time.time() * 1000))

    def _sign(self, message: str) -> str:
        mac = hmac.new(self.secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
        return base64.b64encode(mac).decode("utf-8")

    def generate_rest_signature(
        self,
        timestamp_ms: str,
        method: str,
        request_path: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> str:
        # Handle RESTMethod enum - get the value and uppercase it
        method_str = method.value.upper() if hasattr(method, 'value') else str(method).upper()
        query = ""
        if params:
            # WEEX expects query string in the signature for GET with ?...
            query = "?" + urlencode(params, doseq=True)

        body_str = ""
        if body is not None:
            # Stable JSON; do not pretty-print
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)

        payload = f"{timestamp_ms}{method_str}{request_path}{query}{body_str}"
        return self._sign(payload)

    def generate_ws_signature(self, timestamp_ms: str) -> str:
        payload = f"{timestamp_ms}{CONSTANTS.WS_PRIVATE_REQUEST_PATH}"
        return self._sign(payload)

    async def rest_authenticate(self, request):
        """
        Adds ACCESS-* headers for private REST endpoints.
        request.url has full URL; request.throttler_limit_id etc. are handled elsewhere.
        """
        timestamp_ms = self._now_ms()

        # Extract path and query from request.url
        url = str(request.url)
        base = CONSTANTS.REST_URLS[CONSTANTS.DEFAULT_DOMAIN]
        if not url.startswith(base):
            # if somehow a different base is used, fall back to path parsing
            path_and_query = url
        else:
            path_and_query = url[len(base):]

        if "?" in path_and_query:
            request_path, query_str = path_and_query.split("?", 1)
            params = dict([kv.split("=", 1) for kv in query_str.split("&") if "=" in kv])
        else:
            request_path = path_and_query
            params = None

        body = None
        if request.data is not None:
            # request.data may already be a dict, or raw JSON string. Normalize to dict if possible.
            if isinstance(request.data, (dict, list)):
                body = request.data
            else:
                try:
                    body = json.loads(request.data)
                except Exception:
                    body = None

        signature = self.generate_rest_signature(
            timestamp_ms=timestamp_ms,
            method=request.method,
            request_path=request_path,
            params=params,
            body=body if isinstance(body, dict) else None,
        )


        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-TIMESTAMP": timestamp_ms,
            "ACCESS-SIGN": signature,
            "Content-Type": "application/json",
        }
        if self.passphrase:
            headers["ACCESS-PASSPHRASE"] = self.passphrase
        # headers = request.headers or {}
        # headers.update({
        #     "Content-Type": "application/json",
        #     "ACCESS-KEY": self.api_key,
        #     "ACCESS-TIMESTAMP": timestamp_ms,
        #     "ACCESS-SIGN": signature,
        # })
        request.headers = headers
        return request

    async def ws_authenticate(self, request):
        """
        Adds headers for the private WS handshake if the WS assistant supports it.
        """
        timestamp_ms = self._now_ms()
        signature = self.generate_ws_signature(timestamp_ms)

        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-TIMESTAMP": timestamp_ms,
            "ACCESS-SIGN": signature,
            "Content-Type": "application/json",
        }
        if self.passphrase:
            headers["ACCESS-PASSPHRASE"] = self.passphrase
        # headers = request.headers or {}
        # headers.update({
        #     "ACCESS-KEY": self.api_key,
        #     "ACCESS-PASSPHRASE": self.passphrase,
        #     "ACCESS-TIMESTAMP": timestamp_ms,
        #     "ACCESS-SIGN": signature,
        # })
        request.headers = headers
        return request
