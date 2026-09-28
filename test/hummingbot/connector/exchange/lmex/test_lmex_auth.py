"""
Unit tests for LmexAuth.

NOTE on the LMEX docs examples
--------------------------------
The LMEX API documentation shows example signatures computed with keys that are
clearly obfuscated (e.g. the secret ends in "bx" — not valid hex; it is a
placeholder string). We therefore cannot reproduce the documented signatures
with those credentials.

Instead, the tests below verify:
  1. HMAC-SHA384 is used (not SHA-256 or SHA-512).
  2. Signature = HMAC.SHA384(secret, path + nonce + body) — the canonical formula.
  3. Query parameters are NOT included in the signed path (urlparse strips them).
  4. REST headers (request-api / request-nonce / request-sign) are set correctly.
  5. Nonce is expressed as epoch milliseconds (integer, as string).
All tests use a known key pair whose signatures we compute locally, so every
assertion is a deterministic round-trip.
"""
import asyncio
import hashlib
import hmac
import json
import unittest
from unittest.mock import MagicMock

from hummingbot.connector.exchange.lmex.lmex_auth import LmexAuth


# ---------------------------------------------------------------------------
# Known-good test credentials (generated for testing only)
# ---------------------------------------------------------------------------
_TEST_API_KEY = "test_api_key_abcdef1234567890"
_TEST_SECRET = "test_secret_xyz9876543210abcdef"


def _reference_sign(path: str, nonce: str, body: str = "") -> str:
    """Pure-Python reference implementation used to cross-check LmexAuth."""
    message = path + nonce + body
    return hmac.new(
        _TEST_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha384,
    ).hexdigest()


def _make_auth(epoch_ms: int) -> LmexAuth:
    tp = MagicMock()
    tp.time.return_value = epoch_ms / 1e3
    return LmexAuth(api_key=_TEST_API_KEY, secret_key=_TEST_SECRET, time_provider=tp)


def _make_request(url: str, data=None, headers=None):
    req = MagicMock()
    req.url = url
    req.data = data
    req.headers = headers or {}
    return req


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestLmexAuthSignature(unittest.TestCase):

    def test_signature_is_sha384_hex(self):
        """Signature must be a 96-character hex string (SHA-384 = 48 bytes)."""
        auth = _make_auth(1677663813822)
        sig = auth._generate_signature("/api/v3.2/user/open_orders", "1677663813822", "")
        self.assertEqual(96, len(sig))
        # Must be valid hex
        int(sig, 16)  # raises ValueError if not

    def test_signature_formula_path_nonce_body(self):
        """Verify: sign = HMAC-SHA384(secret, path + nonce + body)."""
        path = "/api/v3.2/order"
        nonce = "1677662848553"
        body = json.dumps({"symbol": "BTC-USD", "side": "BUY", "size": "0.001", "type": "LIMIT"})

        auth = _make_auth(int(nonce))
        got = auth._generate_signature(path, nonce, body)
        want = _reference_sign(path, nonce, body)
        self.assertEqual(want, got)

    def test_signature_differs_when_body_differs(self):
        """Adding body content must change the signature (body is part of the signed message)."""
        auth = _make_auth(1234567890000)
        path, nonce = "/api/v3.2/order", "1234567890000"
        sig_no_body = auth._generate_signature(path, nonce, "")
        sig_with_body = auth._generate_signature(path, nonce, '{"size":"1"}')
        self.assertNotEqual(sig_no_body, sig_with_body)

    def test_signature_differs_when_nonce_differs(self):
        """Different nonce must produce different signature (replay-attack protection)."""
        auth_a = _make_auth(1000000)
        auth_b = _make_auth(2000000)
        path = "/api/v3.2/user/open_orders"
        sig_a = auth_a._generate_signature(path, "1000000", "")
        sig_b = auth_b._generate_signature(path, "2000000", "")
        self.assertNotEqual(sig_a, sig_b)

    def test_query_params_excluded_from_signature(self):
        """
        Signing with path+query ≠ signing with path only — confirming that
        rest_authenticate must strip query parameters before signing.
        """
        auth = _make_auth(1677663813822)
        nonce = "1677663813822"
        sig_path = auth._generate_signature("/api/v3.2/user/open_orders", nonce, "")
        sig_with_qs = auth._generate_signature("/api/v3.2/user/open_orders?symbol=BTC-USD", nonce, "")
        self.assertNotEqual(sig_path, sig_with_qs)


class TestLmexAuthRestAuthenticate(unittest.TestCase):

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_sets_request_api_header(self):
        auth = _make_auth(1677663813822)
        req = _make_request("https://api.lmex.io/spot/api/v3.2/user/open_orders")
        result = self._run(auth.rest_authenticate(req))
        self.assertEqual(_TEST_API_KEY, result.headers["request-api"])

    def test_sets_request_nonce_as_epoch_ms_string(self):
        epoch_ms = 1677663813822
        auth = _make_auth(epoch_ms)
        req = _make_request("https://api.lmex.io/spot/api/v3.2/user/open_orders")
        result = self._run(auth.rest_authenticate(req))
        self.assertEqual(str(epoch_ms), result.headers["request-nonce"])

    def test_sets_request_sign_correct_value(self):
        """Signature in header must match reference (path-only, no query params)."""
        epoch_ms = 1677663813822
        nonce = str(epoch_ms)
        url = "https://api.lmex.io/spot/api/v3.2/user/open_orders?symbol=BTC-USD"
        # Only the path, no query string
        expected_sig = _reference_sign("/api/v3.2/user/open_orders", nonce, "")

        auth = _make_auth(epoch_ms)
        req = _make_request(url)
        result = self._run(auth.rest_authenticate(req))
        self.assertEqual(expected_sig, result.headers["request-sign"])

    def test_sets_content_type_json(self):
        auth = _make_auth(1677663813822)
        req = _make_request("https://api.lmex.io/spot/api/v3.2/order")
        result = self._run(auth.rest_authenticate(req))
        self.assertEqual("application/json", result.headers["Content-Type"])

    def test_post_body_included_in_signature(self):
        epoch_ms = 1677662848553
        nonce = str(epoch_ms)
        body = json.dumps({"symbol": "BTC-USD", "side": "BUY", "size": "0.001", "type": "LIMIT"})
        expected_sig = _reference_sign("/api/v3.2/order", nonce, body)

        auth = _make_auth(epoch_ms)
        req = _make_request("https://api.lmex.io/spot/api/v3.2/order", data=body)
        result = self._run(auth.rest_authenticate(req))
        self.assertEqual(expected_sig, result.headers["request-sign"])

    def test_existing_headers_are_preserved(self):
        """Caller-set headers must not be wiped, only auth headers added."""
        auth = _make_auth(1677663813822)
        req = _make_request(
            "https://api.lmex.io/spot/api/v3.2/order",
            headers={"X-Custom": "keep-me"},
        )
        result = self._run(auth.rest_authenticate(req))
        self.assertEqual("keep-me", result.headers["X-Custom"])
        self.assertIn("request-api", result.headers)

    def test_sandbox_url_still_signs_with_path_only(self):
        """test-api.lmex.io URLs must sign with path only (not the full sandbox URL)."""
        epoch_ms = 1677663813822
        nonce = str(epoch_ms)
        path = "/api/v3.2/user/open_orders"
        expected_sig = _reference_sign(path, nonce, "")

        auth = _make_auth(epoch_ms)
        req = _make_request(f"https://test-api.lmex.io/spot{path}")
        result = self._run(auth.rest_authenticate(req))
        self.assertEqual(expected_sig, result.headers["request-sign"])


class TestLmexAuthApiKeyProperty(unittest.TestCase):
    def test_api_key_property(self):
        auth = _make_auth(0)
        self.assertEqual(_TEST_API_KEY, auth.api_key)


if __name__ == "__main__":
    unittest.main()
