import base64
import hashlib
import hmac
import time
from typing import Dict, Any

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class SwaphereAuth(AuthBase):
    """
    Auth class for Swaphere exchange
    """
    def __init__(self, api_key: str, secret_key: str, passphrase: str = ""):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the auth headers for REST request
        """
        headers = {}
        
        timestamp = str(int(time.time()))
        
        # Create signature payload
        path_url = request.url.path
        if request.params:
            path_url = path_url + "?" + "&".join([f"{k}={v}" for k, v in request.params.items()])
            
        body = ""
        if request.data is not None:
            if isinstance(request.data, dict):
                body = request.data
            else:
                body = request.data.decode()
                
        # Full signature string
        message = timestamp + request.method + path_url + (body if body else "")
        
        # Create signature
        signature = base64.b64encode(
            hmac.new(
                self.secret_key.encode(),
                message.encode(),
                hashlib.sha256
            ).digest()
        ).decode()
        
        # Add auth headers
        headers = {
            "SWAPHERE-API-KEY": self.api_key,
            "SWAPHERE-API-SIGN": signature,
            "SWAPHERE-API-TIMESTAMP": timestamp,
        }
        
        if self.passphrase:
            headers["SWAPHERE-API-PASSPHRASE"] = self.passphrase
            
        # Add to request headers
        if request.headers:
            request.headers.update(headers)
        else:
            request.headers = headers
            
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Adds auth info to the websocket connection request
        """
        timestamp = str(int(time.time()))
        
        # Create signature for websocket
        signature_string = timestamp + "GET" + "/users/self/verify"
        
        signature = base64.b64encode(
            hmac.new(
                self.secret_key.encode(),
                signature_string.encode(),
                hashlib.sha256
            ).digest()
        ).decode()
        
        auth_params = {
            "op": "login",
            "args": [{
                "apiKey": self.api_key,
                "passphrase": self.passphrase,
                "timestamp": timestamp,
                "sign": signature
            }]
        }
        
        # Add auth params to the payload
        request.payload = auth_params
        
        return request 