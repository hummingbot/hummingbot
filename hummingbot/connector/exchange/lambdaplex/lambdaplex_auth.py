import base64
import json
import textwrap
from typing import Any, Dict, List, Tuple, Union

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hummingbot.connector.exchange.lambdaplex import lambdaplex_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest, WSRequest


class LambdaplexAuth(AuthBase):
    def __init__(self, api_key: str, private_key: str, time_provider: TimeSynchronizer):
        self._api_key = api_key
        self._pem_private_key = self._load_pem_private_key(private_key=private_key) if private_key else ""
        self._time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        if request.method == RESTMethod.POST:
            request.params = self._add_auth_to_args(args=json.loads(request.data or "{}"))
            request.data = None
        else:
            request.params = self._add_auth_to_args(args=dict(request.params or {}))

        request.headers = dict(request.headers or {})
        request.headers["X-API-KEY"] = self._api_key

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        if not isinstance(request, WSJSONRequest):
            raise NotImplementedError("Lambdaplex connector only handles authentication for JSON WebSocket messages.")
        if request.payload["method"] != CONSTANTS.WS_SESSION_LOGON_METHOD:
            raise NotImplementedError(
                f"Only the {CONSTANTS.WS_SESSION_LOGON_METHOD} needs authentication for Lambdaplex."
            )

        params = request.payload.get("params") or {}
        params["apiKey"] = self._api_key
        request.payload["params"] = self._add_auth_to_args(args=params)

        return request

    def _add_auth_to_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        args["recvWindow"] = CONSTANTS.RECEIVE_WINDOW
        args["timestamp"] = int(self._time_provider.time() * 1e3)

        arg_pairs = [(k, str(v)) for (k, v) in args.items()]

        args["signature"] = self._sign_param_pairs(arg_pairs=arg_pairs)

        return args

    def _sign_param_pairs(self, arg_pairs: List[Tuple[str, Union[str, int, float]]]) -> str:
        payload_string = "&".join(f"{k}={v}" for k, v in arg_pairs)
        try:
            sig_bytes = self._pem_private_key.sign(payload_string.encode("ascii"))
        except UnicodeEncodeError:
            # Fallback if non-ASCII sneaks in
            sig_bytes = self._pem_private_key.sign(payload_string.encode("utf-8"))
        return base64.b64encode(sig_bytes).decode("ascii")

    def _load_pem_private_key(self, private_key: str) -> Ed25519PrivateKey:
        private_key_pem_str = self._prepare_private_key_pem_str(private_key=private_key)

        try:
            key = serialization.load_pem_private_key(
                private_key_pem_str.encode("utf-8"),
                password=None,
            )
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid private key format or unsupported key type: {e}")

        if not isinstance(key, Ed25519PrivateKey):
            raise TypeError("The provided key is not an Ed25519 private key.")

        return key

    @staticmethod
    def _prepare_private_key_pem_str(private_key: str) -> str:
        """
        Normalizes a provided Ed25519 private key string into proper PEM format.
        Handles raw base64 strings, escaped newlines, and already PEM-formatted keys.
        """
        # Clean input and unescape literal \n
        key_str = private_key.strip().replace("\\n", "\n")

        # Case 1: already PEM formatted (BEGIN/END markers present)
        if "BEGIN" in key_str and "PRIVATE KEY" in key_str:
            return key_str

        # Case 2: looks like base64-encoded key (no headers)
        # Remove any stray header/footer lines if partially included
        key_b64 = key_str.replace("-----BEGIN PRIVATE KEY-----", "").replace(
            "-----END PRIVATE KEY-----", ""
        ).replace("\n", "").strip()

        # Validate that it’s valid base64
        try:
            base64.b64decode(key_b64, validate=True)
        except Exception as e:
            raise ValueError(f"Invalid private key: not valid base64 ({e})")

        # Wrap at 64 chars per line for proper PEM formatting
        wrapped_key = "\n".join(textwrap.wrap(key_b64, 64))

        # Return properly wrapped PEM
        pem = f"-----BEGIN PRIVATE KEY-----\n{wrapped_key}\n-----END PRIVATE KEY-----"
        return pem
