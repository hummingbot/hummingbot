import time
import uuid
from typing import Any, Dict, Optional

from eth_account import Account
from eth_account.messages import encode_defunct, encode_typed_data

from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class EvedexPerpetualAuth(AuthBase):
    """
    Authentication handler for EVEDEX perpetual exchange.

    EVEDEX uses:
    1. SIWE (Sign-In with Ethereum) for session authentication
    2. EIP-712 typed data signing for order submission
    3. JWT bearer token from auth-api for REST calls
    """

    EIP712_LIMIT_ORDER_TYPES = {
        "Order": [
            {"name": "id", "type": "string"},
            {"name": "instrument", "type": "string"},
            {"name": "side", "type": "string"},
            {"name": "leverage", "type": "uint256"},
            {"name": "quantity", "type": "uint256"},
            {"name": "limitPrice", "type": "uint256"},
            {"name": "chainId", "type": "uint256"},
        ],
    }

    EIP712_MARKET_ORDER_TYPES = {
        "Order": [
            {"name": "id", "type": "string"},
            {"name": "instrument", "type": "string"},
            {"name": "side", "type": "string"},
            {"name": "timeInForce", "type": "string"},
            {"name": "leverage", "type": "uint256"},
            {"name": "cashQuantity", "type": "uint256"},
            {"name": "chainId", "type": "uint256"},
        ],
    }

    # Price/quantity multiplier (18 decimal places for EVM)
    PRICE_MULTIPLIER = 10 ** 18

    def __init__(self, private_key: str, testnet: bool = False):
        self._private_key = private_key
        self._testnet = testnet
        self._chain_id = CONSTANTS.TESTNET_CHAIN_ID if testnet else CONSTANTS.CHAIN_ID
        self._jwt_token: Optional[str] = None
        self._user_exchange_id: Optional[str] = None
        self._token_expiry: float = 0.0

        # Derive address from private key
        self._account = Account.from_key(private_key)
        self._address = self._account.address

    @property
    def address(self) -> str:
        return self._address

    @property
    def user_exchange_id(self) -> Optional[str]:
        return self._user_exchange_id

    @property
    def chain_id(self) -> int:
        return self._chain_id

    def get_eip712_domain(self) -> Dict[str, Any]:
        return {
            "name": CONSTANTS.EIP712_DOMAIN_NAME,
            "version": CONSTANTS.EIP712_DOMAIN_VERSION,
            "chainId": self._chain_id,
        }

    def to_matcher_number(self, value: float) -> int:
        """Convert decimal to 18-decimal integer for EIP-712 signing."""
        return int(round(value * self.PRICE_MULTIPLIER))

    def sign_limit_order(
        self,
        order_id: str,
        instrument: str,
        side: str,
        leverage: int,
        quantity: float,
        limit_price: float,
    ) -> Dict[str, Any]:
        """Sign a limit order with EIP-712."""
        qty_int = self.to_matcher_number(quantity)
        price_int = self.to_matcher_number(limit_price)

        message = {
            "id": order_id,
            "instrument": instrument,
            "side": side,
            "leverage": leverage,
            "quantity": qty_int,
            "limitPrice": price_int,
            "chainId": self._chain_id,
        }

        structured_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                ],
                **self.EIP712_LIMIT_ORDER_TYPES,
            },
            "primaryType": "Order",
            "domain": self.get_eip712_domain(),
            "message": message,
        }

        encoded = encode_typed_data(full_message=structured_data)
        signed = self._account.sign_message(encoded)

        return {
            "id": order_id,
            "instrument": instrument,
            "side": side,
            "leverage": leverage,
            "quantity": qty_int,
            "limitPrice": price_int,
            "chainId": self._chain_id,
            "signature": signed.signature.hex(),
        }

    def sign_market_order(
        self,
        order_id: str,
        instrument: str,
        side: str,
        leverage: int,
        cash_quantity: float,
        time_in_force: str = "IOC",
    ) -> Dict[str, Any]:
        """Sign a market order with EIP-712."""
        cash_int = self.to_matcher_number(cash_quantity)

        message = {
            "id": order_id,
            "instrument": instrument,
            "side": side,
            "timeInForce": time_in_force,
            "leverage": leverage,
            "cashQuantity": cash_int,
            "chainId": self._chain_id,
        }

        structured_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                ],
                **self.EIP712_MARKET_ORDER_TYPES,
            },
            "primaryType": "Order",
            "domain": self.get_eip712_domain(),
            "message": message,
        }

        encoded = encode_typed_data(full_message=structured_data)
        signed = self._account.sign_message(encoded)

        return {
            "id": order_id,
            "instrument": instrument,
            "side": side,
            "timeInForce": time_in_force,
            "leverage": leverage,
            "cashQuantity": cash_int,
            "chainId": self._chain_id,
            "signature": signed.signature.hex(),
        }

    def set_jwt_token(self, token: str, user_exchange_id: str, ttl_seconds: int = 3600):
        """Store JWT token received after SIWE login."""
        self._jwt_token = token
        self._user_exchange_id = user_exchange_id
        self._token_expiry = time.time() + ttl_seconds - 60

    def is_authenticated(self) -> bool:
        return bool(self._jwt_token) and time.time() < self._token_expiry

    def get_auth_headers(self) -> Dict[str, str]:
        if self._jwt_token:
            return {"Authorization": f"Bearer {self._jwt_token}"}
        return {}

    def generate_order_id(self) -> str:
        return f"HBOT-{uuid.uuid4().hex[:16]}"

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers.update(self.get_auth_headers())
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request
