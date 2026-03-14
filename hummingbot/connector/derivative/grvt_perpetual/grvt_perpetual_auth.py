import hashlib
import hmac
import time
from collections import OrderedDict
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class GRVTPerpetualAuth(AuthBase):
    """
    Auth class required by GRVT Perpetual API
    """

    def __init__(self, api_key: str, api_secret: str, time_provider: Optional[TimeSynchronizer] = None):
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._time_provider: Optional[TimeSynchronizer] = time_provider

    def generate_signature(self, method: str, path: str, params: Dict[str, Any] = None) -> str:
        """
        Generate signature for GRVT API authentication.
        
        GRVT uses HMAC-SHA256 signature with the following format:
        {method}{path}{query_string}{body}{timestamp}
        """
        # Sort parameters
        sorted_params = OrderedDict(sorted((params or {}).items()))
        
        # Create query string
        query_string = urlencode(sorted_params)
        
        # Get timestamp in milliseconds
        timestamp = str(int(time.time() * 1000))
        
        # Create message to sign
        message = f"{method}{path}"
        if query_string:
            message += f"?{query_string}"
        message += timestamp
        
        # Generate signature
        secret = bytes(self._api_secret.encode("utf-8"))
        signature = hmac.new(secret, message.encode("utf-8"), hashlib.sha256).hexdigest()
        
        return signature

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Add authentication headers and parameters to REST request.
        """
        timestamp = str(int(time.time() * 1000))
        
        # Get path from URL
        url = request.url
        path = url.split("?")[0] if "?" in url else url
        
        # Remove base URL to get path
        for base_url in ["https://api.grvt.io", "https://api-testnet.grvt.io"]:
            if base_url in path:
                path = path.replace(base_url, "")
                break
        
        # Parse params from URL if present
        params = dict(request.params) if request.params else {}
        if "?" in request.url:
            query_params = request.url.split("?")[1].split("&")
            for param in query_params:
                if "=" in param:
                    key, value = param.split("=", 1)
                    params[key] = value
        
        # Generate signature
        method = request.method.value.upper()
        signature = self.generate_signature(method, path, params)
        
        # Add authentication headers
        if request.headers is None:
            request.headers = {}
        request.headers["GRVT-API-KEY"] = self._api_key
        request.headers["GRVT-TIMESTAMP"] = timestamp
        request.headers["GRVT-SIGNATURE"] = signature
        
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Add authentication to WebSocket request.
        For WebSocket, authentication is handled differently - typically through the connection URL.
        """
        return request

    def get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for requests.
        """
        timestamp = str(int(time.time() * 1000))
        signature = self.generate_signature("GET", "/", {})
        
        return {
            "GRVT-API-KEY": self._api_key,
            "GRVT-TIMESTAMP": timestamp,
            "GRVT-SIGNATURE": signature,
        }

    def header_for_authentication(self) -> Dict[str, str]:
        return {"GRVT-API-KEY": self._api_key}
