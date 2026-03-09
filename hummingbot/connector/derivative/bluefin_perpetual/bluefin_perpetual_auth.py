"""
Authentication module for Bluefin Perpetual connector.

The Bluefin SDK handles authentication internally via JWT tokens.
This AuthBase implementation serves as a thin wrapper to integrate
with hummingbot's authentication system.
"""
from typing import Dict, Any

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class BluefinPerpetualAuth(AuthBase):
    """
    Authentication class for Bluefin Perpetual API.

    The Bluefin SDK manages authentication internally using:
    1. SuiWallet (created from mnemonic)
    2. JWT token obtained via signature-based login
    3. Automatic token refresh

    This class stores the credentials and provides them to the SDK data source.
    """

    def __init__(self, wallet_mnemonic: str, network: str):
        """
        Initialize Bluefin authentication.

        :param wallet_mnemonic: 24-word mnemonic phrase
        :param network: Network name ("MAINNET" or "STAGING")
        """
        self._wallet_mnemonic = wallet_mnemonic
        self._network = network

    @property
    def wallet_mnemonic(self) -> str:
        """Get wallet mnemonic."""
        return self._wallet_mnemonic

    @property
    def network(self) -> str:
        """Get network name."""
        return self._network

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Add authentication to REST request.

        Note: The Bluefin SDK handles REST authentication internally via JWT.
        This method is a no-op for compatibility with hummingbot's auth system.

        :param request: REST request
        :return: Unchanged request
        """
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Add authentication to WebSocket request.

        Note: The Bluefin SDK handles WebSocket authentication internally via JWT.
        This method is a no-op for compatibility with hummingbot's auth system.

        :param request: WebSocket request
        :return: Unchanged request
        """
        return request

    def get_headers(self) -> Dict[str, Any]:
        """
        Get authentication headers.

        Note: The Bluefin SDK manages JWT headers internally.
        Returns empty dict for compatibility.

        :return: Empty dict
        """
        return {}
