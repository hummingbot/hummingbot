import hashlib
import hmac
import time
from typing import Any, Dict, Optional

from eth_account import Account
from eth_account.messages import encode_typed_data

from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class AevoPerpetualAuth(AuthBase):
    """
    Auth class for Aevo Perpetual API.
    Supports both HMAC signature authentication for REST and EIP-712 signing for orders.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        signing_key: Optional[str] = None,
        is_testnet: bool = False,
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._signing_key = signing_key
        self._is_testnet = is_testnet
        self._signing_wallet = None
        if signing_key:
            self._signing_wallet = Account.from_key(signing_key)

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def signing_address(self) -> Optional[str]:
        if self._signing_wallet:
            return self._signing_wallet.address
        return None

    def _get_timestamp_ns(self) -> int:
        """Returns current timestamp in nanoseconds."""
        return int(time.time() * 1e9)

    def _generate_signature(
        self,
        timestamp: int,
        method: str,
        path: str,
        body: str = "",
    ) -> str:
        """
        Generate HMAC SHA256 signature for REST API authentication.
        Message format: apiKey,timestamp,httpMethod,path,body
        """
        message = f"{self._api_key},{timestamp},{method.upper()},{path},{body}"
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def get_auth_headers(
        self,
        method: str,
        path: str,
        body: str = "",
    ) -> Dict[str, str]:
        """
        Generate authentication headers for REST API requests.
        """
        timestamp = self._get_timestamp_ns()
        signature = self._generate_signature(timestamp, method, path, body)
        return {
            "AEVO-KEY": self._api_key,
            "AEVO-TIMESTAMP": str(timestamp),
            "AEVO-SIGNATURE": signature,
        }

    def sign_order(
        self,
        maker: str,
        is_buy: bool,
        limit_price: int,
        amount: int,
        salt: int,
        instrument: int,
        timestamp: int,
    ) -> Dict[str, Any]:
        """
        Sign an order using EIP-712 typed data signing.
        """
        if not self._signing_wallet:
            raise ValueError("Signing key not provided")

        domain_name = CONSTANTS.TESTNET_DOMAIN_NAME if self._is_testnet else CONSTANTS.MAINNET_DOMAIN_NAME
        chain_id = CONSTANTS.TESTNET_CHAIN_ID if self._is_testnet else CONSTANTS.MAINNET_CHAIN_ID

        typed_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                ],
                "Order": [
                    {"name": "maker", "type": "address"},
                    {"name": "isBuy", "type": "bool"},
                    {"name": "limitPrice", "type": "uint256"},
                    {"name": "amount", "type": "uint256"},
                    {"name": "salt", "type": "uint256"},
                    {"name": "instrument", "type": "uint256"},
                    {"name": "timestamp", "type": "uint256"},
                ],
            },
            "primaryType": "Order",
            "domain": {
                "name": domain_name,
                "version": CONSTANTS.DOMAIN_VERSION,
                "chainId": chain_id,
            },
            "message": {
                "maker": maker,
                "isBuy": is_buy,
                "limitPrice": limit_price,
                "amount": amount,
                "salt": salt,
                "instrument": instrument,
                "timestamp": timestamp,
            },
        }

        encoded = encode_typed_data(full_message=typed_data)
        signed = self._signing_wallet.sign_message(encoded)

        return {
            "signature": signed.signature.hex(),
            "r": hex(signed.r),
            "s": hex(signed.s),
            "v": signed.v,
        }

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Add authentication headers to REST request.
        """
        method = request.method.name if hasattr(request.method, "name") else str(request.method)
        path = request.url.split(CONSTANTS.PERPETUAL_BASE_URL)[-1].split(CONSTANTS.TESTNET_BASE_URL)[-1]
        if "?" in path:
            path = path.split("?")[0]

        body = request.data if request.data else ""
        if isinstance(body, dict):
            import json
            body = json.dumps(body)

        headers = self.get_auth_headers(method, path, body)

        if request.headers is None:
            request.headers = {}
        request.headers.update(headers)

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        WebSocket authentication - pass through as auth is done via subscription message.
        """
        return request

    def get_ws_auth_payload(self) -> Dict[str, Any]:
        """
        Generate WebSocket authentication payload.
        """
        timestamp = self._get_timestamp_ns()
        signature = self._generate_signature(timestamp, "GET", "/ws", "")
        return {
            "op": "auth",
            "data": {
                "key": self._api_key,
                "timestamp": str(timestamp),
                "signature": signature,
            },
        }
