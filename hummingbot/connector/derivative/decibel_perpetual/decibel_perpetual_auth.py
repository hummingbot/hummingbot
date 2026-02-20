"""
Authentication module for Decibel Perpetual connector.

Decibel uses:
- Bearer token for REST API (read-only)
- Sec-Websocket-Protocol header for WebSocket auth
- Aptos on-chain transactions for order placement/cancellation (signed with Ed25519 private key)
"""

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class DecibelPerpetualAuth(AuthBase):
    """
    Auth class for Decibel Perpetual API.

    REST: Bearer token + Origin header
    WebSocket: Sec-Websocket-Protocol header
    Orders: On-chain Aptos transactions (handled in derivative class)
    """

    def __init__(
        self,
        api_key: str,
        account_address: str,
        subaccount_address: str,
        private_key: str,
    ):
        self._api_key = api_key
        self._account_address = account_address
        self._subaccount_address = subaccount_address
        self._private_key = private_key

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def account_address(self) -> str:
        return self._account_address

    @property
    def subaccount_address(self) -> str:
        return self._subaccount_address

    @property
    def private_key(self) -> str:
        return self._private_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """Add Bearer token and Origin header to REST requests."""
        if request.headers is None:
            request.headers = {}
        request.headers["Authorization"] = f"Bearer {self._api_key}"
        request.headers["Origin"] = "https://netna-app.decibel.trade/trade"
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """WebSocket auth is handled via Sec-Websocket-Protocol during connection."""
        return request

    def get_ws_protocols(self) -> list:
        """Return the WebSocket sub-protocols for Sec-Websocket-Protocol header."""
        return ["decibel", self._api_key]
