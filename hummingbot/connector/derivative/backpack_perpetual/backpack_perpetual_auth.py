import base64
import time
from typing import Any, Dict
from urllib.parse import urlencode

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest

try:
    from nacl.signing import SigningKey
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False


class BackpackPerpetualAuth(AuthBase):
    """
    Auth class required by Backpack Exchange API.

    Backpack uses ED25519 signature-based authentication with headers:
    - X-API-Key: Base64-encoded public key
    - X-Signature: Base64-encoded ED25519 signature
    - X-Timestamp: Unix timestamp in milliseconds
    - X-Window: Request validity window in milliseconds (default 5000)
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        time_provider: TimeSynchronizer
    ) -> None:
        self._api_key: str = api_key
        self._secret_key: str = secret_key
        self._time_provider: TimeSynchronizer = time_provider
        self._window: int = 5000  # 5 second validity window

        # Initialize signing key if nacl is available
        if NACL_AVAILABLE and secret_key:
            try:
                # Secret key should be base64-encoded ED25519 private key
                key_bytes = base64.b64decode(secret_key)
                self._signing_key = SigningKey(key_bytes[:32])
            except Exception:
                self._signing_key = None
        else:
            self._signing_key = None

    def _build_signature_payload(
        self,
        instruction: str,
        timestamp: int,
        window: int,
        params: Dict[str, Any] = None
    ) -> str:
        """
        Build the signature payload according to Backpack's spec:
        instruction + sorted params + timestamp + window
        """
        parts = [f"instruction={instruction}"]

        if params:
            # Sort params alphabetically and add to payload
            sorted_params = sorted(params.items(), key=lambda x: x[0])
            for key, value in sorted_params:
                if value is not None:
                    parts.append(f"{key}={value}")

        parts.append(f"timestamp={timestamp}")
        parts.append(f"window={window}")

        return "&".join(parts)

    def _generate_signature(self, payload: str) -> str:
        """Generate ED25519 signature for the payload."""
        if not self._signing_key:
            return ""

        try:
            signed = self._signing_key.sign(payload.encode("utf-8"))
            signature = base64.b64encode(signed.signature).decode("utf-8")
            return signature
        except Exception:
            return ""

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        timestamp = int(self._time_provider.time() * 1e3)

        # Determine instruction based on endpoint
        path = request.throttler_limit_id or ""
        if "order" in path.lower():
            if request.method == RESTMethod.POST:
                instruction = "orderExecute"
            elif request.method == RESTMethod.DELETE:
                instruction = "orderCancel"
            else:
                instruction = "orderQuery"
        elif "capital" in path.lower():
            instruction = "balanceQuery"
        elif "position" in path.lower():
            instruction = "positionQuery"
        else:
            instruction = "accountQuery"

        # Build params for signature
        params = {}
        if request.params:
            params.update(request.params)
        if request.data and isinstance(request.data, dict):
            params.update(request.data)

        # Generate signature
        payload = self._build_signature_payload(instruction, timestamp, self._window, params)
        signature = self._generate_signature(payload)

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self._api_key,
            "X-Timestamp": str(timestamp),
            "X-Window": str(self._window),
            "X-Signature": signature,
        }

        request.headers.update(headers)
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request

    def get_ws_auth_payload(self) -> Dict[str, Any]:
        """
        Generates authentication payload for WebSocket connection.
        """
        timestamp = int(self._time_provider.time() * 1e3)
        payload = self._build_signature_payload("subscribe", timestamp, self._window)
        signature = self._generate_signature(payload)

        return {
            "method": "subscribe",
            "params": ["account"],
            "signature": [self._api_key, signature, str(timestamp), str(self._window)]
        }
