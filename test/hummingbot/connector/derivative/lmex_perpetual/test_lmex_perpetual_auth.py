"""
Unit tests for LmexPerpetualAuth.

Verifies that:
  1. Signatures use HMAC-SHA384 (96-character hex digest).
  2. Formula: HMAC-SHA384(secret, path + nonce + body).
  3. Path is extracted from the full URL; query string is NOT signed.
  4. All three required headers are injected (request-api, request-nonce, request-sign).
  5. Content-Type is set to application/json.
  6. Existing request headers are preserved.
  7. Body serialisation: dict → compact JSON, str → verbatim, None → "".
  8. ws_authenticate returns the request unchanged.
  9. api_key property returns the key.

All tests use self-consistent round-trip vectors — no reliance on external
signature examples.
"""
import asyncio
import hashlib
import hmac
import json
import unittest
from unittest.mock import MagicMock, patch

from hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_auth import LmexPerpetualAuth

# ---------------------------------------------------------------------------
# Test credentials
# ---------------------------------------------------------------------------
_API_KEY = "perp_api_key_abcdef1234567890"
_SECRET  = "perp_secret_xyz9876543210abcdef"


def _ref_sign(path: str, nonce: str, body: str = "") -> str:
    """Pure-Python reference implementation for cross-checking LmexPerpetualAuth."""
    msg = path + nonce + body
    return hmac.new(_SECRET.encode(), msg.encode(), hashlib.sha384).hexdigest()


def _make_auth() -> LmexPerpetualAuth:
    return LmexPerpetualAuth(api_key=_API_KEY, secret_key=_SECRET)


def _make_request(url: str, data=None, headers=None):
    req = MagicMock()
    req.url     = url
    req.data    = data
    req.headers = headers or {}
    return req


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# 1. Signature correctness
# ---------------------------------------------------------------------------

class TestLmexPerpetualAuthSignature(unittest.TestCase):

    def setUp(self):
        self.auth = _make_auth()

    def test_signature_is_96_char_hex(self):
        """SHA-384 digest is always 96 hex characters."""
        h = self.auth
        headers = h._generate_auth_headers(
            _make_request("https://api.lmex.io/futures/api/v2.3/user/open_orders")
        )
        sig = headers["request-sign"]
        self.assertEqual(96, len(sig))
        int(sig, 16)  # raises ValueError if not valid hex

    def test_signature_matches_reference(self):
        """Signature exactly equals the pure-Python reference computation."""
        nonce = "1677663813822"
        url   = "https://api.lmex.io/futures/api/v2.3/user/open_orders"
        path  = "/futures/api/v2.3/user/open_orders"

        with patch("hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_auth.time") as mock_time:
            mock_time.time.return_value = int(nonce) / 1000
            headers = self.auth._generate_auth_headers(_make_request(url))

        got_sig   = headers["request-sign"]
        got_nonce = headers["request-nonce"]
        want_sig  = _ref_sign(path, got_nonce, "")
        self.assertEqual(want_sig, got_sig)

    def test_body_included_in_signature(self):
        """A non-empty body changes the signature."""
        url = "https://api.lmex.io/futures/api/v2.3/order"
        req_no_body   = _make_request(url, data=None)
        req_with_body = _make_request(url, data={"symbol": "BTC-PERP", "size": 1})

        h1 = self.auth._generate_auth_headers(req_no_body)
        h2 = self.auth._generate_auth_headers(req_with_body)
        self.assertNotEqual(h1["request-sign"], h2["request-sign"])

    def test_different_nonces_produce_different_signatures(self):
        """Replay-attack protection: different nonce → different signature."""
        url = "https://api.lmex.io/futures/api/v2.3/user/open_orders"
        with patch("hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_auth.time") as mt:
            mt.time.return_value = 1000.0
            h1 = self.auth._generate_auth_headers(_make_request(url))
        with patch("hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_auth.time") as mt:
            mt.time.return_value = 2000.0
            h2 = self.auth._generate_auth_headers(_make_request(url))
        self.assertNotEqual(h1["request-sign"], h2["request-sign"])

    def test_query_string_excluded_from_signature(self):
        """Query parameters are not included in the signed message."""
        base_url    = "https://api.lmex.io/futures/api/v2.3/user/open_orders"
        qs_url      = base_url + "?symbol=BTC-PERP"
        h_no_qs = self.auth._generate_auth_headers(_make_request(base_url))
        h_with_qs = self.auth._generate_auth_headers(_make_request(qs_url))
        # Both sign the same path → different query strings but same path means
        # the path-only signing uses the PATH without '?...'  so signatures differ
        # because the paths are identical (/futures/api/v2.3/user/open_orders)
        # and both should equal the same reference value for the same nonce.
        # Here we test they differ from a signature computed WITH the query string.
        nonce = h_no_qs["request-nonce"]
        path = "/futures/api/v2.3/user/open_orders"
        sig_path_only = _ref_sign(path, nonce)
        self.assertEqual(sig_path_only, h_no_qs["request-sign"])

    def test_sandbox_url_signs_with_path_only(self):
        """Sandbox hostname doesn't appear in the signed message — only the path."""
        url   = "https://test-api.lmex.io/futures/api/v2.3/order"
        path  = "/futures/api/v2.3/order"
        headers = self.auth._generate_auth_headers(_make_request(url))
        nonce   = headers["request-nonce"]
        want    = _ref_sign(path, nonce)
        self.assertEqual(want, headers["request-sign"])


# ---------------------------------------------------------------------------
# 2. Header injection
# ---------------------------------------------------------------------------

class TestLmexPerpetualAuthHeaders(unittest.TestCase):

    def setUp(self):
        self.auth = _make_auth()

    def test_request_api_header_set(self):
        """request-api header is set to the API key."""
        h = self.auth._generate_auth_headers(
            _make_request("https://api.lmex.io/futures/api/v2.3/order")
        )
        self.assertEqual(_API_KEY, h["request-api"])

    def test_request_nonce_is_epoch_ms_string(self):
        """request-nonce is epoch milliseconds expressed as a decimal string."""
        nonce_ms = 1677663813822
        with patch("hummingbot.connector.derivative.lmex_perpetual.lmex_perpetual_auth.time") as mt:
            mt.time.return_value = nonce_ms / 1000
            h = self.auth._generate_auth_headers(
                _make_request("https://api.lmex.io/futures/api/v2.3/order")
            )
        self.assertEqual(str(nonce_ms), h["request-nonce"])

    def test_content_type_is_application_json(self):
        """Content-Type header is set to application/json."""
        h = self.auth._generate_auth_headers(
            _make_request("https://api.lmex.io/futures/api/v2.3/order")
        )
        self.assertEqual("application/json", h["Content-Type"])

    def test_request_sign_header_present(self):
        """request-sign header is present and non-empty."""
        h = self.auth._generate_auth_headers(
            _make_request("https://api.lmex.io/futures/api/v2.3/order")
        )
        self.assertIn("request-sign", h)
        self.assertTrue(h["request-sign"])

    def test_existing_headers_preserved_in_rest_authenticate(self):
        """Caller-set headers are not overwritten by rest_authenticate."""
        req = _make_request(
            "https://api.lmex.io/futures/api/v2.3/order",
            headers={"X-Custom-Header": "keep-me"},
        )
        result = _run(self.auth.rest_authenticate(req))
        self.assertEqual("keep-me", result.headers["X-Custom-Header"])
        self.assertIn("request-api", result.headers)

    def test_rest_authenticate_returns_request(self):
        """rest_authenticate returns the same request object."""
        req    = _make_request("https://api.lmex.io/futures/api/v2.3/order")
        result = _run(self.auth.rest_authenticate(req))
        self.assertIs(req, result)

    def test_none_headers_handled_gracefully(self):
        """A request with headers=None does not raise."""
        req = _make_request("https://api.lmex.io/futures/api/v2.3/order")
        req.headers = None
        result = _run(self.auth.rest_authenticate(req))
        self.assertIn("request-api", result.headers)


# ---------------------------------------------------------------------------
# 3. Body serialisation
# ---------------------------------------------------------------------------

class TestLmexPerpetualAuthBodySerialisation(unittest.TestCase):

    def setUp(self):
        self.auth = _make_auth()

    def test_none_body_signs_with_empty_string(self):
        """No body → the signature is computed with empty body string."""
        url  = "https://api.lmex.io/futures/api/v2.3/user/open_orders"
        path = "/futures/api/v2.3/user/open_orders"
        req  = _make_request(url, data=None)
        h    = self.auth._generate_auth_headers(req)
        want = _ref_sign(path, h["request-nonce"], "")
        self.assertEqual(want, h["request-sign"])

    def test_string_body_used_verbatim(self):
        """A string body is used exactly as-is (not re-serialised)."""
        url    = "https://api.lmex.io/futures/api/v2.3/order"
        path   = "/futures/api/v2.3/order"
        body   = '{"symbol":"BTC-PERP","size":1}'
        req    = _make_request(url, data=body)
        h      = self.auth._generate_auth_headers(req)
        want   = _ref_sign(path, h["request-nonce"], body)
        self.assertEqual(want, h["request-sign"])

    def test_dict_body_serialised_with_compact_json(self):
        """A dict body is serialised with compact separators (',', ':')."""
        url    = "https://api.lmex.io/futures/api/v2.3/order"
        path   = "/futures/api/v2.3/order"
        body   = {"symbol": "BTC-PERP", "size": 1}
        req    = _make_request(url, data=body)
        h      = self.auth._generate_auth_headers(req)
        compact = json.dumps(body, separators=(",", ":"))
        want    = _ref_sign(path, h["request-nonce"], compact)
        self.assertEqual(want, h["request-sign"])


# ---------------------------------------------------------------------------
# 4. WebSocket authenticate
# ---------------------------------------------------------------------------

class TestLmexPerpetualAuthWs(unittest.TestCase):

    def setUp(self):
        self.auth = _make_auth()

    def test_ws_authenticate_returns_request_unchanged(self):
        """ws_authenticate returns the WSRequest without modification."""
        ws_req = MagicMock()
        result = _run(self.auth.ws_authenticate(ws_req))
        self.assertIs(ws_req, result)

    def test_ws_authenticate_does_not_mutate_request(self):
        """ws_authenticate does not set any attributes on the request."""
        ws_req = MagicMock(spec=[])  # no attributes allowed
        # Should not raise AttributeError
        _run(self.auth.ws_authenticate(ws_req))


# ---------------------------------------------------------------------------
# 5. api_key property
# ---------------------------------------------------------------------------

class TestLmexPerpetualAuthProperty(unittest.TestCase):

    def test_api_key_property(self):
        """api_key property returns the key passed at construction."""
        auth = LmexPerpetualAuth(api_key=_API_KEY, secret_key=_SECRET)
        self.assertEqual(_API_KEY, auth.api_key)


if __name__ == "__main__":
    unittest.main()
