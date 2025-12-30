import base64
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class BackpackAuth(AuthBase):
    """
    Auth class for Backpack Exchange using ED25519 signatures.

    Backpack uses ED25519 keypairs for authentication:
    - API Key: Base64-encoded public key
    - Signature: Base64-encoded ED25519 signature of the request
    """

    def __init__(self, api_key: str, api_secret: str):
        """
        Initialize BackpackAuth.

        Args:
            api_key: Base64-encoded ED25519 public key
            api_secret: Base64-encoded ED25519 private key (or raw hex/bytes)
        """
        self._api_key = api_key
        self._api_secret = api_secret
        self._private_key = self._load_private_key(api_secret)

    def _load_private_key(self, secret: str) -> Ed25519PrivateKey:
        """
        Load ED25519 private key from various formats.

        Supports:
        - Base64-encoded raw private key bytes (32 bytes)
        - Hex-encoded private key
        """
        try:
            # Try base64 decode first
            key_bytes = base64.b64decode(secret)
            if len(key_bytes) == 32:
                # Raw 32-byte private key
                return Ed25519PrivateKey.from_private_bytes(key_bytes)
            elif len(key_bytes) == 64:
                # Some formats include public key appended (first 32 bytes are private)
                return Ed25519PrivateKey.from_private_bytes(key_bytes[:32])
            else:
                # Try as PEM format
                return serialization.load_pem_private_key(key_bytes, password=None)
        except Exception:
            pass

        try:
            # Try hex decode
            key_bytes = bytes.fromhex(secret)
            if len(key_bytes) == 32:
                return Ed25519PrivateKey.from_private_bytes(key_bytes)
            elif len(key_bytes) == 64:
                return Ed25519PrivateKey.from_private_bytes(key_bytes[:32])
        except Exception:
            pass

        raise ValueError(
            "Unable to load ED25519 private key. Expected base64 or hex encoded 32-byte key."
        )

    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds."""
        return int(time.time() * 1000)

    def _sign_message(self, message: str) -> str:
        """
        Sign a message with ED25519 private key.

        Args:
            message: The message string to sign

        Returns:
            Base64-encoded signature
        """
        message_bytes = message.encode("utf-8")
        signature = self._private_key.sign(message_bytes)
        return base64.b64encode(signature).decode("utf-8")

    def _build_signing_string(
        self,
        instruction: str,
        params: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None,
        window: int = CONSTANTS.DEFAULT_WINDOW,
    ) -> str:
        """
        Build the signing string for Backpack API.

        Format: instruction=<type>&param1=value1&...&timestamp=<ts>&window=<window>
        Parameters must be alphabetically sorted.

        Args:
            instruction: The API instruction type (e.g., "orderExecute")
            params: Request parameters (body or query)
            timestamp: Unix timestamp in milliseconds
            window: Validity window in milliseconds

        Returns:
            The signing string
        """
        if timestamp is None:
            timestamp = self._get_timestamp()

        # Start with instruction
        parts = [f"instruction={instruction}"]

        # Add sorted params
        if params:
            # Sort parameters alphabetically by key
            sorted_params = sorted(params.items(), key=lambda x: x[0])
            for key, value in sorted_params:
                if value is not None:
                    # Convert booleans and other types to appropriate string format
                    if isinstance(value, bool):
                        str_value = "true" if value else "false"
                    else:
                        str_value = str(value)
                    parts.append(f"{key}={str_value}")

        # Add timestamp and window
        parts.append(f"timestamp={timestamp}")
        parts.append(f"window={window}")

        return "&".join(parts)

    def generate_auth_headers(
        self,
        instruction: str,
        params: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None,
        window: int = CONSTANTS.DEFAULT_WINDOW,
    ) -> Dict[str, str]:
        """
        Generate authentication headers for a request.

        Args:
            instruction: The API instruction type
            params: Request parameters
            timestamp: Unix timestamp in milliseconds (generated if None)
            window: Validity window in milliseconds

        Returns:
            Dictionary of auth headers
        """
        if timestamp is None:
            timestamp = self._get_timestamp()

        # Build signing string
        signing_string = self._build_signing_string(
            instruction=instruction,
            params=params,
            timestamp=timestamp,
            window=window,
        )

        # Sign
        signature = self._sign_message(signing_string)

        return {
            "X-API-Key": self._api_key,
            "X-Signature": signature,
            "X-Timestamp": str(timestamp),
            "X-Window": str(window),
        }

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Add authentication to a REST request.

        Note: The instruction type must be set in request.data["_instruction"]
        or determined from the endpoint.
        """
        # Determine instruction from request data or endpoint
        instruction = None
        params = {}

        if request.data:
            if isinstance(request.data, dict):
                # Extract instruction if provided
                instruction = request.data.pop("_instruction", None)
                params = dict(request.data)
            elif isinstance(request.data, str):
                import json
                try:
                    data_dict = json.loads(request.data)
                    instruction = data_dict.pop("_instruction", None)
                    params = data_dict
                except json.JSONDecodeError:
                    pass

        if request.params:
            params.update(request.params)

        # Default instruction mapping based on method and URL
        if instruction is None:
            instruction = self._infer_instruction(request.method, request.url, params)

        if instruction:
            auth_headers = self.generate_auth_headers(
                instruction=instruction,
                params=params if params else None,
            )
            if request.headers is None:
                request.headers = {}
            request.headers.update(auth_headers)

        return request

    def _infer_instruction(
        self,
        method: RESTMethod,
        url: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Infer the instruction type from the request method and URL.
        """
        url_lower = url.lower()

        if CONSTANTS.ORDER_URL in url_lower or CONSTANTS.ORDERS_URL in url_lower:
            if method == RESTMethod.POST:
                return CONSTANTS.INSTRUCTION_ORDER_EXECUTE
            elif method == RESTMethod.DELETE:
                if "orders" in url_lower:
                    return CONSTANTS.INSTRUCTION_ORDER_CANCEL_ALL
                return CONSTANTS.INSTRUCTION_ORDER_CANCEL
            elif method == RESTMethod.GET:
                if params and "orderId" in params:
                    return CONSTANTS.INSTRUCTION_ORDER_QUERY
                return CONSTANTS.INSTRUCTION_ORDER_QUERY_ALL
        elif CONSTANTS.CAPITAL_URL in url_lower:
            return CONSTANTS.INSTRUCTION_BALANCE_QUERY
        elif CONSTANTS.ACCOUNT_URL in url_lower:
            return CONSTANTS.INSTRUCTION_ACCOUNT_QUERY

        return None

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Add authentication to a WebSocket request.

        For Backpack, WebSocket authentication is done via a signed subscription message.
        """
        return request  # WebSocket auth is handled separately in subscription messages

    def generate_ws_auth_payload(
        self,
        streams: list[str],
    ) -> Dict[str, Any]:
        """
        Generate a signed payload for WebSocket private stream subscription.

        Args:
            streams: List of stream names to subscribe to

        Returns:
            Signed subscription payload
        """
        timestamp = self._get_timestamp()
        window = CONSTANTS.DEFAULT_WINDOW

        # Build signing string for subscription
        # For WebSocket, the instruction is "subscribe"
        signing_string = self._build_signing_string(
            instruction="subscribe",
            params=None,
            timestamp=timestamp,
            window=window,
        )

        signature = self._sign_message(signing_string)

        return {
            "method": "SUBSCRIBE",
            "params": streams,
            "signature": [self._api_key, signature, str(timestamp), str(window)],
        }

    def generate_ws_unsubscribe_payload(self, streams: list[str]) -> Dict[str, Any]:
        """
        Generate payload for WebSocket unsubscription.

        Args:
            streams: List of stream names to unsubscribe from

        Returns:
            Unsubscription payload
        """
        return {
            "method": "UNSUBSCRIBE",
            "params": streams,
        }
