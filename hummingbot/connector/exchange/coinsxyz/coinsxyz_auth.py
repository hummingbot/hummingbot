"""
Authentication module for Coins.xyz Exchange Connector

This module handles HMAC-SHA256 authentication for Coins.xyz API requests,
including request signing and header management.
"""

import hashlib
import hmac
import json
from collections import OrderedDict
from typing import Any, Dict, Optional
from urllib.parse import urlencode

# Production Hummingbot imports
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class CoinsxyzAuth(AuthBase):
    """
    Authentication class for Coins.xyz API requests.

    Implements HMAC-SHA256 signature generation and request authentication
    following Coins.xyz API specifications.
    """

    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer = None):
        """
        Initialize the authentication handler.

        :param api_key: The API key provided by Coins.xyz
        :param secret_key: The secret key provided by Coins.xyz
        :param time_provider: Time synchronizer for accurate timestamps
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider or TimeSynchronizer()

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds authentication information to REST API requests.

        This method adds the required timestamp, signature, and headers
        for authenticated interactions with the Coins.xyz API.

        :param request: The request to be authenticated
        :return: The authenticated request
        """
        # For Coins.xyz, all authenticated requests use query parameters
        if request.data:
            if isinstance(request.data, str):
                params = json.loads(request.data)
            else:
                params = request.data
        else:
            params = request.params or {}

        # Add auth params (timestamp + signature)
        request.params = self.add_auth_to_params(params=params)

        # Clear data for POST requests since params go in query string
        if request.method == RESTMethod.POST:
            request.data = None

        # Add authentication headers
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication())
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Authenticate WebSocket requests.

        Note: Coins.xyz may not require WebSocket authentication for public streams.
        This method can be extended if private WebSocket streams require authentication.

        :param request: The WebSocket request to authenticate
        :return: The authenticated WebSocket request
        """
        return request  # Pass-through for now

    def add_auth_to_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add authentication parameters to the request.

        :param params: Original request parameters
        :return: Parameters with authentication data added
        """
        # Get current timestamp in milliseconds
        import time
        timestamp = int(time.time() * 1000)

        # Create ordered dictionary to ensure consistent parameter ordering
        request_params = OrderedDict(params or {})
        request_params["timestamp"] = timestamp

        # Generate signature
        signature = self._generate_signature(params=request_params)
        request_params["signature"] = signature

        return request_params

    def header_for_authentication(self) -> Dict[str, str]:
        """
        Generate authentication headers for API requests.

        :return: Dictionary containing authentication headers
        """
        return {
            "X-COINS-APIKEY": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "hummingbot-coinsxyz-connector/1.0"
        }

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generate HMAC-SHA256 signature for API request authentication.

        The signature is created by:
        1. Converting parameters to URL-encoded query string
        2. Creating HMAC-SHA256 hash using the secret key
        3. Converting to hexadecimal string

        :param params: Request parameters to sign
        :return: HMAC-SHA256 signature as hexadecimal string
        """
        # Convert parameters to URL-encoded query string
        encoded_params_str = urlencode(params)

        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.secret_key.encode("utf8"),
            encoded_params_str.encode("utf8"),
            hashlib.sha256
        ).hexdigest()

        return signature

    def get_headers_for_public_request(self) -> Dict[str, str]:
        """
        Get headers for public API requests (no authentication required).

        :return: Dictionary containing public request headers
        """
        return {
            "Content-Type": "application/json",
            "User-Agent": "Hummingbot/CoinsxyzConnector"
        }

    def validate_credentials(self) -> bool:
        """
        Validate that API credentials are properly configured.

        :return: True if credentials are valid, False otherwise
        """
        return (
            self.api_key is not None and
            len(self.api_key.strip()) > 0 and
            self.secret_key is not None and
            len(self.secret_key.strip()) > 0
        )

    def get_timestamp(self) -> int:
        """
        Get current timestamp in milliseconds for API requests.

        Uses the time synchronizer to get server-synchronized time.

        :return: Current synchronized timestamp in milliseconds
        """
        return int(self.time_provider.time() * 1000)

    def validate_timestamp(self, timestamp: int, tolerance_ms: int = 60000) -> bool:
        """
        Validate if a timestamp is within acceptable range.

        :param timestamp: Timestamp to validate (milliseconds)
        :param tolerance_ms: Acceptable time difference (milliseconds)
        :return: True if timestamp is valid
        """
        current_time_ms = self.get_timestamp()
        time_diff_ms = abs(timestamp - current_time_ms)

        return time_diff_ms <= tolerance_ms

    def get_auth_headers(self, method: str, url: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Generate authentication headers for a specific request.

        Args:
            method: HTTP method
            url: Request URL
            data: Request data

        Returns:
            Dictionary of authentication headers
        """
        # Get base headers
        headers = self.header_for_authentication()

        # Add signature if credentials are available
        if self.validate_credentials():
            timestamp = self.get_timestamp()
            # Create params dict for signature generation
            params = data.copy() if data else {}
            params['timestamp'] = timestamp
            signature = self._generate_signature(params)

            headers.update({
                "X-COINS-APIKEY": self.api_key,
                "X-COINS-TIMESTAMP": str(timestamp),
                "X-COINS-SIGNATURE": signature
            })

        return headers

    def is_timestamp_valid(self, timestamp: int) -> bool:
        """
        Validate if a timestamp is within acceptable range.

        Args:
            timestamp: Timestamp in milliseconds

        Returns:
            True if timestamp is valid, False otherwise
        """
        import time
        current_time = int(time.time() * 1000)
        # Allow 5 minute window (300,000 ms)
        time_diff = abs(current_time - timestamp)
        return time_diff <= 300000
