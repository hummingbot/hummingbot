import hmac
import hashlib
import time
import json
from typing import Dict, Any, Optional
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest

class AevoPerpetualAuth(AuthBase):
    def __init__(self, api_key: str, api_secret: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.api_secret = api_secret
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = {}
        if request.headers:
            headers.update(request.headers)
        
        # Precision is Key! Aevo expects nanoseconds.
        # Ensure we multiply by 1e9 and cast to int before string.
        timestamp = str(int(self.time_provider.time() * 1e9))
        signature = self._generate_signature(timestamp, request.method, request.url, request.data)
        
        headers.update({
            "AEVO-ACCESS-KEY": self.api_key,
            "AEVO-ACCESS-SIG": signature,
            "AEVO-ACCESS-TIMESTAMP": timestamp,
        })
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # Websocket auth often handled differently, checking docs

    def _generate_signature(self, timestamp: str, method: str, url: str, data: Optional[Dict[str, Any]]) -> str:
        # Aevo specific signature generation (check docs for exact format)
        # Typically: HMAC-SHA256(secret, timestamp + method + path + body)
        payload = f"{timestamp}{method.upper()}{url}"
        if data:
            payload += json.dumps(data, separators=(',', ':'))
            
        return hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
