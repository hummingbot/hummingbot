import time
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

import eth_account
from eth_account.messages import encode_typed_data

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class GrvtPerpetualAuth(AuthBase):
    """
    Handles authentication for the GRVT Perpetual API.

    GRVT uses two auth mechanisms:
    1. Session cookie — obtained by POSTing API key to the edge auth endpoint.
       The cookie is attached to all subsequent trade-data requests.
    2. EIP-712 order signatures — every order must be signed with the wallet
       private key before submission.
    """

    EIP712_ORDER_TYPES = {
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

    def __init__(
        self,
        api_key: str,
        api_secret: str,  # wallet private key
        sub_account_id: str,
        domain: str = CONSTANTS.DOMAIN,
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._sub_account_id = sub_account_id
        self._domain = domain
        self._is_testnet = domain == CONSTANTS.TESTNET_DOMAIN
        self._chain_id = CONSTANTS.CHAIN_ID_TESTNET if self._is_testnet else CONSTANTS.CHAIN_ID_PROD
        self._session_cookie: Optional[str] = None
        self._wallet = eth_account.Account.from_key(api_secret)
        self._nonce_counter = int(time.time()) % (2 ** 32)

    @property
    def wallet_address(self) -> str:
        return self._wallet.address

    def get_next_nonce(self) -> int:
        self._nonce_counter = (self._nonce_counter + 1) % (2 ** 32)
        return self._nonce_counter

    def set_session_cookie(self, cookie: str):
        self._session_cookie = cookie

    def sign_order(
        self,
        sub_account_id: int,
        is_market: bool,
        time_in_force: int,
        post_only: bool,
        reduce_only: bool,
        legs: list,
        nonce: int,
        expiration: int,
    ) -> Dict[str, Any]:
        """
        Signs an order using EIP-712 and returns the signature dict.
        legs items must already have contractSize and limitPrice as integers
        (multiplied by their respective multipliers).
        """
        domain_data = {
            "name": CONSTANTS.EIP712_DOMAIN_NAME,
            "version": CONSTANTS.EIP712_DOMAIN_VERSION,
            "chainId": self._chain_id,
        }
        message = {
            "subAccountID": sub_account_id,
            "isMarket": is_market,
            "timeInForce": time_in_force,
            "postOnly": post_only,
            "reduceOnly": reduce_only,
            "legs": legs,
            "nonce": nonce,
            "expiration": expiration,
        }
        signable = encode_typed_data(domain_data, self.EIP712_ORDER_TYPES, message)
        signed = self._wallet.sign_message(signable)
        return {
            "r": "0x" + signed.r.to_bytes(32, "big").hex(),
            "s": "0x" + signed.s.to_bytes(32, "big").hex(),
            "v": signed.v,
            "signer": self._wallet.address,
            "nonce": nonce,
            "expiration": expiration,
        }

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        if self._session_cookie:
            request.headers["Cookie"] = self._session_cookie
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # WS auth is handled via the session cookie in the subscribe message

    def get_auth_payload(self) -> Dict[str, Any]:
        """Returns the payload for the session cookie login request."""
        return {
            "api_key": self._api_key,
            "sub_account_id": self._sub_account_id,
        }


def price_to_int(price: Decimal) -> int:
    """Convert a price to GRVT's integer representation (multiply by 1e9)."""
    return int(price * Decimal(CONSTANTS.PRICE_MULTIPLIER))


def size_to_int(size: Decimal, base_decimals: int = 9) -> int:
    """Convert a contract size to GRVT's integer representation."""
    return int(size * Decimal(10 ** base_decimals))
