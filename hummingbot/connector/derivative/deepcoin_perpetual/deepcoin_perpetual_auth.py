import hashlib
import hmac
import base64
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class DeepcoinPerpetualAuth(AuthBase):
    """
    Auth class required by Deepcoin Perpetual API
    """

    def __init__(self, api_key: str, secret_key: str, passphrase: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions.
        """
        return self.add_auth_headers(method=request.method, request=request)

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated.
        """
        return self.generate_ws_auth_message()

    def get_referral_code_headers(self):
        """
        Generates referral headers
        """
        headers = {
            "referer": CONSTANTS.HBOT_BROKER_ID
        }
        return headers

    def add_auth_headers(self, method: RESTMethod, request: Optional[Dict[str, Any]]):
        """
        Add authentication headers in request object
        """
        # Generate ISO format timestamp as required by Deepcoin API
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        headers = {}
        headers["DC-ACCESS-KEY"] = self.api_key
        headers["DC-ACCESS-TIMESTAMP"] = timestamp
        headers["DC-ACCESS-PASSPHRASE"] = self.passphrase
        
        # Get request path from the request URL
        request_path = request.url.path if hasattr(request, 'url') else ""
        
        if method == RESTMethod.POST:
            signature = self._generate_rest_signature(
                timestamp=timestamp, method=method, request_path=request_path, payload=request.data)
        else:
            signature = self._generate_rest_signature(
                timestamp=timestamp, method=method, request_path=request_path, payload=request.params)
        
        headers["DC-ACCESS-SIGN"] = signature
        headers["Content-Type"] = "application/json"

        # TODO brokerid need to be add to the headers
        request.headers = {**request.headers, **headers} if request.headers is not None else headers
        return request

    def _generate_rest_signature(self, timestamp: str, method: RESTMethod, request_path: str, payload: Optional[Dict[str, Any]]) -> str:
        """
        Generate signature for Deepcoin Perpetual API requests
        According to Deepcoin API docs: timestamp + method + requestPath + body
        """
        if payload is None:
            payload = {}
        
        # For GET requests, parameters are part of requestPath, not body
        if method == RESTMethod.GET:
            # For GET requests, body is empty as parameters are in URL
            body = ""
        else:
            # For POST requests, body is the JSON payload
            body = str(payload) if payload else ""
        
        # Create signature string: timestamp + method + requestPath + body
        param_str = timestamp + method.value + request_path + body
            
        signature = hmac.new(
            bytes(self.secret_key, "utf-8"),
            param_str.encode("utf-8"),
            digestmod="sha256"
        ).digest()
        return base64.b64encode(signature).decode("utf-8")

    def _generate_ws_signature(self, expires: int):
        """
        Generate WebSocket signature for Deepcoin
        """
        # For WebSocket, we need to use the same signature method as REST API
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        param_str = timestamp + "GET" + "/realtime" + str(expires)
        
        signature = hmac.new(
            bytes(self.secret_key, "utf-8"),
            param_str.encode("utf-8"),
            digestmod="sha256"
        ).digest()
        return base64.b64encode(signature).decode("utf-8")

    def generate_ws_auth_message(self):
        """
        Generates the authentication message to start receiving messages from private ws channels
        """
        expires = int((self._time() + 10000) * 1000)
        signature = self._generate_ws_signature(expires)
        auth_message = {
            "op": "auth",
            "args": [self.api_key, expires, signature]
        }
        return auth_message

    def _time(self):
        return time.time()
