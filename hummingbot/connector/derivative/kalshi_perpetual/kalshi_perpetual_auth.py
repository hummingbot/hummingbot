import base64
import re
import textwrap
from typing import Dict
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest

# Matches a PEM block whatever its label (PKCS#1 "RSA PRIVATE KEY" or PKCS#8 "PRIVATE KEY") so a key whose line
# breaks were lost when pasted into a single-line prompt can be re-wrapped.
_PEM_BLOCK_PATTERN = re.compile(r"-----BEGIN ([A-Z0-9 ]+)-----(.*?)-----END \1-----", re.DOTALL)


class KalshiPerpetualAuth(AuthBase):
    """
    Kalshi signs every authenticated REST request and the WebSocket handshake with the same three headers:
    an RSA-PSS (SHA-256) signature over timestamp_ms + HTTP method + path, where the path excludes the query string.
    https://docs.kalshi.com/getting_started/api_keys
    """

    def __init__(self, api_key: str, private_key: str, time_provider: TimeSynchronizer):
        self._api_key: str = api_key
        self._private_key: RSAPrivateKey = self._load_private_key(private_key)
        self._time_provider: TimeSynchronizer = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        auth_headers = self.header_for_authentication(method=request.method.value, path=urlparse(request.url).path)
        request.headers = {**request.headers, **auth_headers} if request.headers is not None else auth_headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        # Kalshi authenticates the WebSocket once, at handshake time, with header_for_authentication().
        return request  # pass-through

    def header_for_authentication(self, method: str, path: str) -> Dict[str, str]:
        timestamp = str(int(self._time_provider.time() * 1e3))
        return {
            "KALSHI-ACCESS-KEY": self._api_key,
            "KALSHI-ACCESS-SIGNATURE": self._generate_signature(f"{timestamp}{method.upper()}{path}"),
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }

    def _generate_signature(self, message: str) -> str:
        signature = self._private_key.sign(
            message.encode("utf-8"),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    @staticmethod
    def _load_private_key(private_key: str) -> RSAPrivateKey:
        pem = private_key.strip().replace("\\n", "\n")
        match = _PEM_BLOCK_PATTERN.search(pem)
        if match is None:
            raise ValueError("The Kalshi private key must be a PEM-encoded RSA key.")
        label, body = match.group(1), "".join(match.group(2).split())
        pem = f"-----BEGIN {label}-----\n" + "\n".join(textwrap.wrap(body, 64)) + f"\n-----END {label}-----\n"

        key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
        if not isinstance(key, RSAPrivateKey):
            raise TypeError("The Kalshi private key must be an RSA key.")
        return key
