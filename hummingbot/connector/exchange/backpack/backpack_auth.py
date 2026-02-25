"""Backpack authentication module using ED25519 signing."""
import base64
import json
from collections import OrderedDict
from typing import Any, Dict
from urllib.parse import urlencode

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class BackpackAuth(AuthBase):
    """
    Authentication class for Backpack Exchange API.
    
    Backpack uses ED25519 keypair signing for authentication.
    All authenticated requests must include a signature generated using the secret key.
    """

    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer = None):
        """
        Initializes the BackpackAuth.

        :param api_key: The API key for Backpack
        :param secret_key: The secret key (base64 encoded private key) for signing
        :param time_provider: Optional time synchronizer for timestamp generation
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider
        
        # Try to import ed25519 for signing
        try:
            from nacl.signing import SigningKey
            self._signing_key = SigningKey(base64.b64decode(secret_key))
        except ImportError:
            # Fallback: signature will be handled by external method
            self._signing_key = None
        except Exception:
            self._signing_key = None

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds authentication to a REST request.
        
        :param request: The request to authenticate
        :return: The authenticated request
        """
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication())
        request.headers = headers
        
        # Add signature to request
        if request.method == RESTMethod.POST:
            if request.data:
                data = json.loads(request.data) if isinstance(request.data, str) else request.data
                signed_data = self.add_auth_to_params(data, request.url, "POST")
                request.data = json.dumps(signed_data)
        else:
            request.params = self.add_auth_to_params(request.params or {}, request.url, request.method.value)
        
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Adds authentication to a WebSocket request.
        
        :param request: The request to authenticate
        :return: The authenticated request
        """
        # WebSocket authentication is handled via subscription messages
        return request

    def add_auth_to_params(self, params: Dict[str, Any], url: str, method: str) -> Dict[str, Any]:
        """
        Adds authentication parameters to the request params.
        
        :param params: The request parameters
        :param url: The request URL
        :param method: The HTTP method
        :return: The parameters with authentication added
        """
        timestamp = self._get_timestamp()
        
        request_params = OrderedDict(params or {})
        
        # Add timestamp if not present
        if "timestamp" not in request_params:
            request_params["timestamp"] = timestamp
        
        # Generate signature
        signature = self._generate_signature(
            method=method,
            url=url,
            params=request_params,
            timestamp=timestamp,
        )
        request_params["signature"] = signature
        
        return request_params

    def header_for_authentication(self) -> Dict[str, str]:
        """
        Returns the headers required for authentication.
        
        :return: Dictionary of authentication headers
        """
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _get_timestamp(self) -> int:
        """
        Gets the current timestamp in milliseconds.
        
        :return: Timestamp in milliseconds
        """
        import time
        if self.time_provider:
            return int(self.time_provider.time() * 1000)
        return int(time.time() * 1000)

    def _generate_signature(self, method: str, url: str, params: Dict[str, Any], timestamp: int) -> str:
        """
        Generates the ED25519 signature for a request.
        
        Backpack signature format:
        instruction={method}\n\
        headerTimestamp={timestamp}\n\
        {url}\n\
        {body (if present)}
        
        :param method: HTTP method
        :param url: Request URL
        :param params: Request parameters
        :param timestamp: Request timestamp
        :return: Base64 encoded signature
        """
        # Build the message to sign
        message_parts = [
            f"instruction={method.upper()}",
            f"headerTimestamp={timestamp}",
            url,
        ]
        
        # Add body for POST requests
        if method.upper() == "POST" and params:
            # Remove signature from params if present
            body_params = {k: v for k, v in params.items() if k != "signature"}
            if body_params:
                body = json.dumps(body_params, separators=(',', ':'))
                message_parts.append(body)
        
        message = "\n".join(message_parts)
        
        # Sign the message
        if self._signing_key:
            try:
                from nacl.signing import SigningKey
                signature_bytes = self._signing_key.sign(message.encode("utf-8")).signature
                return base64.b64encode(signature_bytes).decode("utf-8")
            except Exception:
                pass
        
        # Fallback: return empty signature (will fail on server)
        return ""

    def generate_websocket_auth_message(self) -> Dict[str, Any]:
        """
        Generates the authentication message for WebSocket connections.
        
        :return: Authentication message dictionary
        """
        timestamp = self._get_timestamp()
        
        # Build the message to sign for WebSocket
        message = f"instruction=subscribe\nheaderTimestamp={timestamp}"
        
        signature = ""
        if self._signing_key:
            try:
                from nacl.signing import SigningKey
                signature_bytes = self._signing_key.sign(message.encode("utf-8")).signature
                signature = base64.b64encode(signature_bytes).decode("utf-8")
            except Exception:
                pass
        
        return {
            "method": "subscribe",
            "signature": signature,
            "apiKey": self.api_key,
            "timestamp": timestamp,
        }
