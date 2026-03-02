import json
import time
from collections import OrderedDict
from typing import Any, Dict, Optional

import eth_account
from eth_account.messages import encode_typed_data
from eth_utils import keccak, to_hex

from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class EvedexPerpetualAuth(AuthBase):
    """
    Auth class required by EVEDEX Perpetual API.
    
    EVEDEX uses EIP-712 Ethereum typed structured data hashing and signing
    for order authentication. Each order must be accompanied by a signature
    field containing a signature made with the user's crypto wallet.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        use_api_key_auth: bool = False
    ):
        """
        Initialize authentication.
        
        Args:
            api_key: Wallet address or API key
            api_secret: Wallet private key or API secret
            use_api_key_auth: If True, use API key authentication instead of wallet signing
        """
        self._api_key: str = api_key
        self._api_secret: str = api_secret
        self._use_api_key_auth = use_api_key_auth
        
        if not use_api_key_auth:
            # Initialize wallet for signing
            self.wallet = eth_account.Account.from_key(api_secret)
            self._wallet_address = self.wallet.address
        else:
            self.wallet = None
            self._wallet_address = api_key

    @property
    def wallet_address(self) -> str:
        """Return the wallet address."""
        return self._wallet_address

    def get_eip712_domain(self, is_mainnet: bool = True) -> Dict[str, Any]:
        """
        Get the EIP-712 domain for signing.
        
        Args:
            is_mainnet: Whether this is for mainnet or testnet
            
        Returns:
            EIP-712 domain dictionary
        """
        chain_id = 1 if is_mainnet else 5  # Mainnet or Goerli testnet
        return {
            "name": "EVEDEX",
            "version": "1",
            "chainId": chain_id,
            "verifyingContract": "0x0000000000000000000000000000000000000000",
        }

    def get_order_types(self) -> Dict[str, list]:
        """
        Get the EIP-712 type definitions for order signing.
        
        Returns:
            Type definitions dictionary
        """
        return {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Order": [
                {"name": "instrument", "type": "string"},
                {"name": "side", "type": "string"},
                {"name": "price", "type": "string"},
                {"name": "quantity", "type": "string"},
                {"name": "orderType", "type": "string"},
                {"name": "timeInForce", "type": "string"},
                {"name": "clientOrderId", "type": "string"},
                {"name": "timestamp", "type": "uint256"},
                {"name": "nonce", "type": "uint256"},
            ],
            "CancelOrder": [
                {"name": "orderId", "type": "string"},
                {"name": "instrument", "type": "string"},
                {"name": "timestamp", "type": "uint256"},
                {"name": "nonce", "type": "uint256"},
            ],
        }

    def sign_typed_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sign typed data using EIP-712.
        
        Args:
            data: The typed data to sign
            
        Returns:
            Signature components (r, s, v)
        """
        if self._use_api_key_auth:
            raise ValueError("Cannot sign with API key authentication mode")
            
        structured_data = encode_typed_data(full_message=data)
        signed = self.wallet.sign_message(structured_data)
        
        return {
            "r": to_hex(signed["r"]),
            "s": to_hex(signed["s"]),
            "v": signed["v"]
        }

    def sign_order(
        self,
        instrument: str,
        side: str,
        price: str,
        quantity: str,
        order_type: str,
        time_in_force: str,
        client_order_id: str,
        is_mainnet: bool = True
    ) -> Dict[str, Any]:
        """
        Sign an order using EIP-712.
        
        Args:
            instrument: Trading pair (e.g., "BTCUSDT")
            side: "buy" or "sell"
            price: Order price
            quantity: Order quantity
            order_type: "limit" or "market"
            time_in_force: "GTC", "IOC", or "FOK"
            client_order_id: Client-generated order ID
            is_mainnet: Whether this is for mainnet
            
        Returns:
            Signed order with signature
        """
        timestamp = int(time.time() * 1000)
        nonce = timestamp
        
        order_message = {
            "instrument": instrument,
            "side": side,
            "price": price,
            "quantity": quantity,
            "orderType": order_type,
            "timeInForce": time_in_force,
            "clientOrderId": client_order_id,
            "timestamp": timestamp,
            "nonce": nonce,
        }
        
        typed_data = {
            "domain": self.get_eip712_domain(is_mainnet),
            "types": self.get_order_types(),
            "primaryType": "Order",
            "message": order_message,
        }
        
        signature = self.sign_typed_data(typed_data)
        
        return {
            **order_message,
            "signature": signature,
            "walletAddress": self._wallet_address,
        }

    def sign_cancel_order(
        self,
        order_id: str,
        instrument: str,
        is_mainnet: bool = True
    ) -> Dict[str, Any]:
        """
        Sign an order cancellation using EIP-712.
        
        Args:
            order_id: The order ID to cancel
            instrument: Trading pair
            is_mainnet: Whether this is for mainnet
            
        Returns:
            Signed cancel request with signature
        """
        timestamp = int(time.time() * 1000)
        nonce = timestamp
        
        cancel_message = {
            "orderId": order_id,
            "instrument": instrument,
            "timestamp": timestamp,
            "nonce": nonce,
        }
        
        typed_data = {
            "domain": self.get_eip712_domain(is_mainnet),
            "types": self.get_order_types(),
            "primaryType": "CancelOrder",
            "message": cancel_message,
        }
        
        signature = self.sign_typed_data(typed_data)
        
        return {
            **cancel_message,
            "signature": signature,
            "walletAddress": self._wallet_address,
        }

    def add_auth_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Add authentication headers for API key mode.
        
        Args:
            headers: Existing headers dictionary
            
        Returns:
            Headers with authentication added
        """
        if self._use_api_key_auth:
            headers["X-API-Key"] = self._api_key
            timestamp = str(int(time.time() * 1000))
            headers["X-Timestamp"] = timestamp
            # For API key auth, sign the timestamp
            message = f"{timestamp}"
            signature = self._generate_api_signature(message)
            headers["X-Signature"] = signature
        else:
            headers["X-Wallet-Address"] = self._wallet_address
        return headers

    def _generate_api_signature(self, message: str) -> str:
        """
        Generate signature for API key authentication.
        
        Args:
            message: Message to sign
            
        Returns:
            Hex-encoded signature
        """
        if self._use_api_key_auth:
            import hmac
            import hashlib
            signature = hmac.new(
                self._api_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            return signature
        return ""

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Add authentication to REST request.
        
        Args:
            request: The REST request to authenticate
            
        Returns:
            Authenticated request
        """
        if request.headers is None:
            request.headers = {}
        
        request.headers = self.add_auth_headers(request.headers)
        
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Add authentication to WebSocket request.
        
        Args:
            request: The WebSocket request to authenticate
            
        Returns:
            Authenticated request (EVEDEX uses Centrifuge JWT auth)
        """
        # EVEDEX WebSocket authentication is handled separately through
        # Centrifuge JWT tokens, so pass-through here
        return request

    def get_ws_auth_payload(self) -> Dict[str, Any]:
        """
        Get WebSocket authentication payload for Centrifuge.
        
        Returns:
            Authentication payload for WebSocket connection
        """
        timestamp = int(time.time() * 1000)
        
        if self._use_api_key_auth:
            return {
                "apiKey": self._api_key,
                "timestamp": timestamp,
                "signature": self._generate_api_signature(str(timestamp)),
            }
        else:
            # For wallet auth, generate a signed message
            message = f"authenticate:{timestamp}"
            message_hash = keccak(text=message)
            signed = self.wallet.signHash(message_hash)
            return {
                "walletAddress": self._wallet_address,
                "timestamp": timestamp,
                "signature": to_hex(signed.signature),
            }

    @staticmethod
    def _get_timestamp() -> float:
        """Get current timestamp."""
        return time.time()
