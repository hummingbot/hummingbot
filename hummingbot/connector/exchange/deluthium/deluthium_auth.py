"""
Authentication for Deluthium DEX connector.

Deluthium uses JWT Bearer token authentication for all API calls.
The JWT token is pre-issued by the Deluthium team - no signing required.
"""

from typing import Any, Dict

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class DeluthiumAuth(AuthBase):
    """
    Auth class for Deluthium API using JWT Bearer token.
    
    Unlike typical exchange APIs that require HMAC signing, Deluthium uses
    pre-issued JWT tokens that are simply added to the Authorization header.
    """

    def __init__(self, api_key: str):
        """
        Initialize with JWT token.
        
        :param api_key: JWT token from Deluthium team
        """
        self._api_key: str = api_key

    @property
    def api_key(self) -> str:
        """Return the API key (JWT token)."""
        return self._api_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Add JWT Bearer token to REST request headers.
        
        All Deluthium API endpoints require JWT authentication.
        
        :param request: The REST request to authenticate
        :return: Authenticated REST request with Authorization header
        """
        headers = request.headers or {}
        headers.update(self._get_auth_headers())
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        WebSocket authentication (pass-through for now).
        
        Deluthium doesn't currently use WebSocket for the RFQ API.
        This is a placeholder for potential future WebSocket support.
        
        :param request: The WebSocket request
        :return: The request unchanged
        """
        return request

    def _get_auth_headers(self) -> Dict[str, Any]:
        """
        Generate authentication headers with JWT Bearer token.
        
        :return: Dictionary with Authorization header
        """
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def get_auth_headers(self) -> Dict[str, str]:
        """
        Public method to get authentication headers.
        
        Useful for external callers that need the headers directly.
        
        :return: Dictionary with Authorization header
        """
        return self._get_auth_headers()
