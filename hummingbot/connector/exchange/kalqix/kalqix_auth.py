import hashlib
import hmac
import json
import os
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlparse

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest

# ---------------------------------------------------------------------------
# BIP-340 Schnorr signing — inline reference implementation
# ---------------------------------------------------------------------------
# The server verifies signatures with `@noble/curves/secp256k1`'s
# `schnorr.verify`, which accepts arbitrary-length messages and feeds them
# straight into BIP-340's tagged hashes. `coincurve.sign_schnorr` is strict
# to spec (32-byte messages only), so we can't use it for our
# variable-length canonical-JSON payloads. This is a 50-line pure-Python
# implementation that matches @noble's lenient behavior byte-for-byte.

_SECP256K1_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_SECP256K1_G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)


def _point_add(P1, P2):
    if P1 is None:
        return P2
    if P2 is None:
        return P1
    if P1[0] == P2[0] and P1[1] != P2[1]:
        return None
    if P1 == P2:
        lam = (3 * P1[0] * P1[0] * pow(2 * P1[1], _SECP256K1_P - 2, _SECP256K1_P)) % _SECP256K1_P
    else:
        lam = ((P2[1] - P1[1]) * pow(P2[0] - P1[0], _SECP256K1_P - 2, _SECP256K1_P)) % _SECP256K1_P
    x3 = (lam * lam - P1[0] - P2[0]) % _SECP256K1_P
    return (x3, (lam * (P1[0] - x3) - P1[1]) % _SECP256K1_P)


def _point_mul(P, scalar):
    R = None
    while scalar:
        if scalar & 1:
            R = _point_add(R, P)
        P = _point_add(P, P)
        scalar >>= 1
    return R


def _tagged_hash(tag: str, msg: bytes) -> bytes:
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + msg).digest()


def _schnorr_sign(privkey_hex: str, message: bytes) -> bytes:
    """BIP-340 Schnorr sign matching `@noble/curves/secp256k1` — accepts
    arbitrary-length `message`. Returns the 64-byte signature."""
    d0 = int(privkey_hex.removeprefix("0x"), 16)
    if not (1 <= d0 <= _SECP256K1_N - 1):
        raise ValueError("Schnorr: private key out of range")
    P = _point_mul(_SECP256K1_G, d0)
    d = d0 if P[1] % 2 == 0 else _SECP256K1_N - d0
    aux_rand = os.urandom(32)
    t = bytes(
        a ^ b for a, b in zip(d.to_bytes(32, "big"), _tagged_hash("BIP0340/aux", aux_rand))
    )
    k0 = int.from_bytes(
        _tagged_hash("BIP0340/nonce", t + P[0].to_bytes(32, "big") + message), "big"
    ) % _SECP256K1_N
    if k0 == 0:
        raise RuntimeError("Schnorr: derived nonce was zero")
    R = _point_mul(_SECP256K1_G, k0)
    k = k0 if R[1] % 2 == 0 else _SECP256K1_N - k0
    e = int.from_bytes(
        _tagged_hash(
            "BIP0340/challenge",
            R[0].to_bytes(32, "big") + P[0].to_bytes(32, "big") + message,
        ),
        "big",
    ) % _SECP256K1_N
    return R[0].to_bytes(32, "big") + ((k + e * d) % _SECP256K1_N).to_bytes(32, "big")


class KalqixAuth(AuthBase):
    """
    Two-layer auth:

    1. **Transport (HMAC-SHA256)**, applied to every REST request:
       signing string `METHOD|PATH|QUERY|BODY|TIMESTAMP` is HMAC-signed
       with `api_secret` and sent as `x-api-key`, `x-api-signature`,
       `x-api-timestamp` headers. PATH excludes the query string. QUERY is
       a sorted-by-key `k=v&k=v` string. BODY is the canonical JSON of the
       request body (sorted keys, no whitespace). TIMESTAMP is ms since
       epoch as a string.

    2. **Payload (BIP-340 Schnorr)**, applied only on state-changing
       requests (place order, cancel, cancel-all): the request body or
       query carries an `agent_index` plus a `signature` produced by
       signing the canonical action payload with the agent-wallet
       private key. This is **not** in the HTTP layer — it lives inside
       the request body or query that the HMAC layer then signs over.

    The exchange class is responsible for assembling the Schnorr-signed
    portion (via `sign_payload` / `agent_index` exposed below) before
    handing the request to the rest-assistant pipeline. This class then
    transparently appends the HMAC headers regardless of action.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        agent_index: int,
        agent_private_key: str,
        time_provider: TimeSynchronizer,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.agent_index = agent_index
        # 32-byte hex (64 chars). Held in memory; never logged.
        self._agent_private_key = agent_private_key
        self.time_provider = time_provider

    # ------------------------------------------------------------------
    # AuthBase contract
    # ------------------------------------------------------------------

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """Add `x-api-*` HMAC headers and canonicalize the on-wire body to
        match what was signed.

        The body is rewritten on the request so wire bytes equal signed
        bytes. The query (request.params) is read but not rewritten — the
        server sorts query params before re-signing, so wire order is
        irrelevant.

        Decomposition matches the Hummingbot Spot Connector v2.1
        Binance-reference layout (`_generate_signature`,
        `header_for_authentication`). Binance's third helper
        `add_auth_to_params` has no analogue here: KalqiX carries the
        signature in headers, not in the query/body.
        """
        timestamp = self._timestamp_ms()
        method = request.method.value.upper() if isinstance(request.method, RESTMethod) else str(request.method).upper()
        path = urlparse(request.url).path

        body_str = self._canonical_body_and_rewrite(request)
        query_str = self._canonical_query(request.params)

        signature = self._generate_signature(method, path, query_str, body_str, timestamp)

        headers = {} if request.headers is None else dict(request.headers)
        headers.update(self.header_for_authentication(signature=signature, timestamp=timestamp))
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        # KalqiX does not expose authenticated WebSocket channels yet.
        return request

    def header_for_authentication(self, signature: str, timestamp: int) -> Dict[str, str]:
        """Return the auth headers KalqiX expects on every authenticated
        REST request. Binance's analogue takes no arguments because
        Binance smuggles the signature into params; KalqiX puts both the
        signature and the timestamp on the headers, so they're passed in.
        """
        return {
            "x-api-key": self.api_key,
            "x-api-signature": signature,
            "x-api-timestamp": str(timestamp),
        }

    def _generate_signature(
        self,
        method: str,
        path: str,
        query_str: str,
        body_str: str,
        timestamp: int,
    ) -> str:
        """HMAC-SHA256 over the canonical signing string
        `METHOD|PATH|QUERY|BODY|TIMESTAMP`. Returns lowercase hex digest.
        """
        signing_string = f"{method}|{path}|{query_str}|{body_str}|{timestamp}"
        return hmac.new(
            self.api_secret.encode("utf-8"),
            signing_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    # ------------------------------------------------------------------
    # Schnorr signing — used by the exchange class for state-changing payloads
    # ------------------------------------------------------------------

    def sign_payload(self, payload: Dict[str, Any]) -> str:
        """Schnorr-sign the canonical form of `payload` with the
        agent-wallet private key. Returns a 64-byte signature as 128 hex
        chars (no `0x` prefix).

        The canonical form is `json.dumps(payload, sort_keys=True,
        separators=(",", ":"))` — exactly what the server reconstructs
        from `JSON.stringify(payload, Object.keys(payload).sort())` for
        flat payloads.

        Note: the server's canonicalizer is technically a "key whitelist"
        rather than a "deep sort", which only matters for nested objects.
        All action payloads we sign are flat, so the two are equivalent.
        """
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        sig_bytes = _schnorr_sign(self._agent_private_key, canonical.encode("utf-8"))
        return sig_bytes.hex()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _timestamp_ms(self) -> int:
        return int(self.time_provider.time() * 1e3)

    def _canonical_body_and_rewrite(self, request: RESTRequest) -> str:
        """Parse request.data, re-emit as canonical JSON, write it back
        onto the request, and return the canonical string for signing.
        """
        data = request.data
        if data is None or data == "":
            return ""
        if isinstance(data, (bytes, bytearray)):
            data = data.decode("utf-8")
        if isinstance(data, str):
            parsed = json.loads(data)
        else:
            parsed = data  # already a dict
        canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
        request.data = canonical
        return canonical

    @staticmethod
    def _canonical_query(params: Optional[Mapping[str, Any]]) -> str:
        if not params:
            return ""
        # Match server's `Object.entries(query).sort((a,b)=>a[0].localeCompare(b[0]))`
        # then `k=v` joined with `&`. No URL-encoding — the server compares
        # raw strings.
        items = sorted(params.items(), key=lambda kv: kv[0])
        return "&".join(f"{k}={v}" for k, v in items)
