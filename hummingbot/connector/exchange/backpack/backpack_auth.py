import base64
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from nacl.signing import SigningKey

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class BackpackAuth(AuthBase):
    """
    Authentication class for Backpack Exchange.
    Uses ED25519 signature-based authentication.
    """

    def __init__(self, api_key: str, api_secret: str):
        """
        Initialize auth with API credentials.

        Args:
            api_key: Base64-encoded ED25519 public key
            api_secret: Base64-encoded ED25519 private key (seed)
        """
        self._api_key = api_key
        self._api_secret = api_secret
        self._signing_key: Optional[SigningKey] = None

        if api_secret:
            try:
                secret_bytes = base64.b64decode(api_secret)
                self._signing_key = SigningKey(secret_bytes)
            except Exception:
                self._signing_key = None

    @property
    def api_key(self) -> str:
        return self._api_key

    def _get_timestamp(self) -> int:
        return int(time.time() * 1000)

    def _generate_signature(
        self,
        instruction: str,
        params: Dict[str, Any],
        timestamp: int,
        window: int = CONSTANTS.DEFAULT_WINDOW,
    ) -> str:
        """
        Generate ED25519 signature for request.

        Signature format:
        instruction + sorted(params as query string) + timestamp + window
        """
        if not self._signing_key:
            return ""

        # Sort params alphabetically and create query string
        sorted_params = sorted(params.items())
        param_str = urlencode(sorted_params) if sorted_params else ""

        # Build message to sign
        message_parts = [instruction]
        if param_str:
            message_parts.append(param_str)
        message_parts.append(f"timestamp={timestamp}")
        message_parts.append(f"window={window}")

        message = "&".join(message_parts)

        # Sign with ED25519
        signed = self._signing_key.sign(message.encode())
        signature = base64.b64encode(signed.signature).decode()

        return signature

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Add authentication headers to REST request.
        """
        if request.headers is None:
            request.headers = {}

        timestamp = self._get_timestamp()
        window = CONSTANTS.DEFAULT_WINDOW

        # Determine instruction type based on method
        method = request.method.value if hasattr(request.method, 'value') else str(request.method)
        path = request.url.split(CONSTANTS.REST_URL)[-1] if CONSTANTS.REST_URL in request.url else request.url

        # Map to Backpack instruction types
        if "order" in path.lower():
            if method == "POST":
                instruction = "orderExecute"
            elif method == "DELETE":
                instruction = "orderCancel"
            else:
                instruction = "orderQuery"
        elif "capital" in path.lower() or "balance" in path.lower():
            instruction = "balanceQuery"
        else:
            instruction = "balanceQuery"  # Default

        # Parse params from request
        params = {}
        if request.data:
            if isinstance(request.data, dict):
                params = request.data
            elif isinstance(request.data, str):
                import json
                try:
                    params = json.loads(request.data)
                except:
                    params = {}

        if request.params:
            params.update(request.params)

        signature = self._generate_signature(instruction, params, timestamp, window)

        request.headers["X-API-Key"] = self._api_key
        request.headers["X-Timestamp"] = str(timestamp)
        request.headers["X-Window"] = str(window)

        if signature:
            request.headers["X-Signature"] = signature

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Add authentication to WebSocket request.
        """
        timestamp = self._get_timestamp()
        window = CONSTANTS.DEFAULT_WINDOW

        instruction = "subscribe"
        params = {}

        signature = self._generate_signature(instruction, params, timestamp, window)

        if request.payload is None:
            request.payload = {}

        request.payload["api_key"] = self._api_key
        request.payload["timestamp"] = timestamp
        request.payload["window"] = window
        request.payload["signature"] = signature

        return request
