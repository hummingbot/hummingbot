import base64
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest

# Backpack uses ED25519 signatures
try:
    from nacl.signing import SigningKey
    from nacl.encoding import Base64Encoder
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False


class BackpackPerpetualAuth(AuthBase):
    """
    Auth class for Backpack Exchange using ED25519 signatures.

    Headers required:
    - X-API-Key: Base64-encoded public key
    - X-Timestamp: Unix timestamp in milliseconds
    - X-Window: Time window for validity (default 5000ms)
    - X-Signature: Base64-encoded ED25519 signature

    Signature format:
    1. Sort params alphabetically into query string
    2. Append &timestamp=<ts>&window=<window>
    3. Prefix with instruction type (e.g., "orderExecute")
    4. Sign with ED25519 private key
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        time_provider: TimeSynchronizer,
        window: int = 5000
    ) -> None:
        self._api_key: str = api_key
        self._secret_key: str = secret_key
        self._time_provider: TimeSynchronizer = time_provider
        self._window: int = window
        self._signing_key: Optional[Any] = None

        if NACL_AVAILABLE and secret_key:
            try:
                seed = base64.b64decode(secret_key)
                self._signing_key = SigningKey(seed)
            except Exception:
                pass

    def _get_timestamp(self) -> int:
        return int(self._time_provider.time() * 1000)

    def _build_signature_payload(
        self,
        instruction: str,
        params: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None
    ) -> str:
        ts = timestamp or self._get_timestamp()
        if params:
            sorted_params = sorted(params.items(), key=lambda x: x[0])
            param_str = urlencode(sorted_params)
            return f"{instruction}{param_str}&timestamp={ts}&window={self._window}"
        return f"{instruction}timestamp={ts}&window={self._window}"

    def _sign(self, message: str) -> str:
        if not NACL_AVAILABLE or not self._signing_key:
            raise RuntimeError("ED25519 not available. Install PyNaCl: pip install pynacl")
        signed = self._signing_key.sign(message.encode(), encoder=Base64Encoder)
        return base64.b64encode(signed.signature).decode()

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        headers = {"Content-Type": "application/json"}
        instruction = ""
        params = {}

        if request.data and isinstance(request.data, dict):
            instruction = request.data.pop("_instruction", "")
            params = {k: v for k, v in request.data.items() if not k.startswith("_")}

        if request.params:
            params.update(request.params)

        if instruction:
            timestamp = self._get_timestamp()
            headers["X-API-Key"] = self._api_key
            headers["X-Timestamp"] = str(timestamp)
            headers["X-Window"] = str(self._window)
            payload = self._build_signature_payload(instruction, params if params else None, timestamp)
            headers["X-Signature"] = self._sign(payload)

        if request.headers:
            request.headers.update(headers)
        else:
            request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request

    def get_ws_auth_payload(self) -> Dict[str, Any]:
        timestamp = self._get_timestamp()
        payload = self._build_signature_payload("subscribe", None, timestamp)
        signature = self._sign(payload)
        return {
            "method": "subscribe",
            "params": ["account"],
            "signature": [self._api_key, signature, str(timestamp), str(self._window)]
        }
