import time
import hashlib
import struct
from typing import Any, Dict, Optional
from eth_account import Account
from eth_account.messages import encode_typed_data

from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class GrvtPerpetualAuth(AuthBase):
    """
    Authentication handler for GRVT perpetual exchange.
    GRVT uses:
    1. API key cookie authentication for REST endpoints
    2. EIP-712 typed data signing for order submission
    """

    def __init__(self, api_key: str, private_key: str, trading_account_id: str, testnet: bool = False):
        self._api_key = api_key
        self._private_key = private_key
        self._trading_account_id = int(trading_account_id)
        self._testnet = testnet
        self._chain_id = CONSTANTS.CHAIN_ID_TESTNET if testnet else CONSTANTS.CHAIN_ID_PROD
        self._session_cookie: Optional[str] = None
        self._cookie_expiry: float = 0.0

    @property
    def trading_account_id(self) -> int:
        return self._trading_account_id

    def get_eip712_domain(self) -> Dict[str, Any]:
        return {
            "name": "GRVT Exchange",
            "version": "0",
            "chainId": self._chain_id,
        }

    def sign_order(
        self,
        sub_account_id: int,
        is_market: bool,
        time_in_force: int,
        post_only: bool,
        reduce_only: bool,
        legs: list,
        expiration_ns: int,
    ) -> Dict[str, Any]:
        """
        Sign an order using EIP-712 typed data signing.

        :param sub_account_id: The sub-account ID
        :param is_market: Whether this is a market order
        :param time_in_force: TIF value (1=GTT, 2=AON, 3=IOC, 4=FOK)
        :param post_only: Post-only flag
        :param reduce_only: Reduce-only flag
        :param legs: List of order legs [{"assetID": int, "contractSize": int, "limitPrice": int, "isBuyingContract": bool}]
        :param expiration_ns: Order expiration in nanoseconds
        :return: Signed order dict ready for API submission
        """
        nonce = int(time.time() * 1000) % (2**32)

        message = {
            "subAccountID": sub_account_id,
            "isMarket": is_market,
            "timeInForce": time_in_force,
            "postOnly": post_only,
            "reduceOnly": reduce_only,
            "legs": legs,
            "nonce": nonce,
            "expiration": expiration_ns,
        }

        types = {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
            ],
            "Order": [
                {"name": "subAccountID", "type": "uint64"},
                {"name": "isMarket", "type": "bool"},
                {"name": "timeInForce", "type": "uint8"},
                {"name": "postOnly", "type": "bool"},
                {"name": "reduceOnly", "type": "bool"},
                {"name": "legs", "type": "OrderLeg[]"},
                {"name": "nonce", "type": "uint32"},
                {"name": "expiration", "type": "int64"},
            ],
            "OrderLeg": [
                {"name": "assetID", "type": "uint256"},
                {"name": "contractSize", "type": "uint64"},
                {"name": "limitPrice", "type": "uint64"},
                {"name": "isBuyingContract", "type": "bool"},
            ],
        }

        structured_data = {
            "types": types,
            "primaryType": "Order",
            "domain": self.get_eip712_domain(),
            "message": message,
        }

        encoded = encode_typed_data(full_message=structured_data)
        signed = Account.sign_message(encoded, private_key=self._private_key)

        return {
            "order": {
                "sub_account_id": str(sub_account_id),
                "is_market": is_market,
                "time_in_force": time_in_force,
                "post_only": post_only,
                "reduce_only": reduce_only,
                "legs": legs,
                "nonce": nonce,
                "expiration": str(expiration_ns),
                "signature": {
                    "signer": Account.from_key(self._private_key).address,
                    "r": "0x" + signed.r.to_bytes(32, "big").hex(),
                    "s": "0x" + signed.s.to_bytes(32, "big").hex(),
                    "v": signed.v,
                    "expiration": str(expiration_ns),
                    "nonce": nonce,
                },
            }
        }

    def price_to_int(self, price: float) -> int:
        """Convert decimal price to GRVT integer format (9 decimal places)."""
        return int(price * 1e9)

    def size_to_int(self, size: float, base_decimals: int = 9) -> int:
        """Convert decimal size to GRVT integer format."""
        return int(size * (10 ** base_decimals))

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """Add session cookie to REST requests for authenticated endpoints."""
        if self._session_cookie and time.time() < self._cookie_expiry:
            if request.headers is None:
                request.headers = {}
            request.headers["Cookie"] = self._session_cookie
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """Add authentication to WebSocket requests."""
        return request

    def set_session_cookie(self, cookie: str, ttl_seconds: int = 3600):
        """Store session cookie received after login."""
        self._session_cookie = cookie
        self._cookie_expiry = time.time() + ttl_seconds - 60  # expire 1min early

    def get_login_payload(self) -> Dict[str, Any]:
        """Build API key login payload for edge endpoint."""
        return {"api_key": self._api_key}
