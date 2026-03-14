from typing import Any, Dict, Optional

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class DecibelPerpetualAuth(AuthBase):
    """
    Authentication handler for Decibel Perpetual exchange.

    Decibel uses:
    - Bearer token (API key from geomi.dev) for all REST endpoint authentication.
    - Aptos on-chain signatures for order placement (handled by transaction builder).
    """

    def __init__(
        self,
        api_wallet_private_key: str,
        main_wallet_public_key: str,
        api_key: str = "",
    ):
        """
        Initialize Decibel auth handler.

        :param api_wallet_private_key: Private key of the API wallet (for signing on-chain transactions).
        :param main_wallet_public_key: Public address of the main wallet (for account lookups).
        :param api_key: Bearer token for REST API access (from geomi.dev).
        """
        self._api_wallet_private_key = api_wallet_private_key
        self._main_wallet_public_key = main_wallet_public_key
        self._api_key = api_key

    @property
    def main_wallet_address(self) -> str:
        """Return the main wallet public address used for account lookups."""
        return self._main_wallet_public_key

    @property
    def api_wallet_address(self) -> str:
        """Return the API wallet address used for signing transactions."""
        # Normalize Aptos addresses to 0x-prefixed 64-hex format
        addr = self._main_wallet_public_key
        if not addr.startswith("0x"):
            addr = "0x" + addr
        return addr

    @property
    def api_key(self) -> str:
        """Return the API Bearer token."""
        return self._api_key

    def get_auth_headers(self) -> Dict[str, str]:
        """Build Authorization headers for REST requests."""
        headers: Dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """Inject Bearer token into REST request headers."""
        if self._api_key:
            if request.headers is None:
                request.headers = {}
            request.headers["Authorization"] = f"Bearer {self._api_key}"
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """WebSocket authentication (not used for Decibel - no WS stream)."""
        return request

    def get_private_key(self) -> str:
        """Return raw private key for transaction signing."""
        return self._api_wallet_private_key
