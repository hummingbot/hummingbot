"""
Unit tests for hummingbot.connector.exchange.lmex.lmex_web_utils.

Covers:
  - public_rest_url: production URL, sandbox URL, slash normalisation,
    leading-slash endpoint, unknown domain fallback
  - private_rest_url: delegates to public_rest_url for production and sandbox
  - is_exchange_information_valid: active=True, active=False, missing key,
    truthy non-bool value

All tests are synchronous; no async machinery required.
No live network calls are made.
"""

import unittest


# ---------------------------------------------------------------------------
# Helpers — read actual constant values from the source so tests stay in sync
# ---------------------------------------------------------------------------

def _prod_base():
    import hummingbot.connector.exchange.lmex.lmex_constants as C
    return C.REST_URLS[C.DEFAULT_DOMAIN]


def _sandbox_base():
    import hummingbot.connector.exchange.lmex.lmex_constants as C
    return C.REST_URLS[C.DOMAIN_SANDBOX]


def _default_domain():
    import hummingbot.connector.exchange.lmex.lmex_constants as C
    return C.DEFAULT_DOMAIN


def _sandbox_domain():
    import hummingbot.connector.exchange.lmex.lmex_constants as C
    return C.DOMAIN_SANDBOX


# ---------------------------------------------------------------------------
# Test class 1 — public_rest_url
# ---------------------------------------------------------------------------

class TestLmexPublicRestUrl(unittest.TestCase):
    """Tests for public_rest_url URL construction."""

    def setUp(self):
        from hummingbot.connector.exchange.lmex.lmex_web_utils import public_rest_url
        self._fn = public_rest_url

    def test_production_url_built_correctly(self):
        """Production URL is the prod base concatenated with a normalised endpoint."""
        url = self._fn("some/endpoint")
        self.assertEqual(url, _prod_base() + "/some/endpoint")

    def test_sandbox_url_built_correctly(self):
        """Sandbox URL is the sandbox base concatenated with a normalised endpoint."""
        url = self._fn("some/endpoint", domain=_sandbox_domain())
        self.assertEqual(url, _sandbox_base() + "/some/endpoint")

    def test_no_double_slash_when_endpoint_has_no_leading_slash(self):
        """A slash is inserted between base and endpoint only once."""
        url = self._fn("path/to/resource")
        self.assertNotIn("//path", url)
        self.assertIn("/path/to/resource", url)

    def test_endpoint_with_leading_slash_not_doubled(self):
        """An endpoint that already starts with '/' does not produce '//'."""
        url = self._fn("/path/to/resource")
        self.assertFalse(url.count("//") > 1,
                         msg=f"Double slash found in URL: {url}")
        self.assertTrue(url.endswith("/path/to/resource"))

    def test_unknown_domain_falls_back_to_production_base(self):
        """An unrecognised domain falls back to the production base URL."""
        url = self._fn("some/endpoint", domain="nonexistent_domain")
        self.assertTrue(url.startswith(_prod_base()),
                        msg=f"Expected prod base; got: {url}")

    def test_default_domain_matches_production(self):
        """Calling with default domain produces same URL as explicit production domain."""
        url_default = self._fn("api/v3.2/time")
        url_explicit = self._fn("api/v3.2/time", domain=_default_domain())
        self.assertEqual(url_default, url_explicit)

    def test_url_starts_with_https(self):
        """Both production and sandbox URLs begin with https://."""
        for domain in (_default_domain(), _sandbox_domain()):
            with self.subTest(domain=domain):
                url = self._fn("health", domain=domain)
                self.assertTrue(url.startswith("https://"),
                                msg=f"URL does not start with https://: {url}")

    def test_endpoint_appended_verbatim_after_normalisation(self):
        """The endpoint path is appended without further modification."""
        endpoint = "api/v3.2/market_summary"
        url = self._fn(endpoint)
        self.assertTrue(url.endswith(endpoint))


# ---------------------------------------------------------------------------
# Test class 2 — private_rest_url
# ---------------------------------------------------------------------------

class TestLmexPrivateRestUrl(unittest.TestCase):
    """Tests that private_rest_url delegates to public_rest_url."""

    def setUp(self):
        from hummingbot.connector.exchange.lmex.lmex_web_utils import (
            private_rest_url,
            public_rest_url,
        )
        self._private = private_rest_url
        self._public = public_rest_url

    def test_private_matches_public_for_production(self):
        """private_rest_url returns the same URL as public_rest_url on production."""
        endpoint = "api/v3.2/order"
        self.assertEqual(
            self._private(endpoint),
            self._public(endpoint),
        )

    def test_private_matches_public_for_sandbox(self):
        """private_rest_url returns the same URL as public_rest_url on sandbox."""
        endpoint = "api/v3.2/order"
        domain = _sandbox_domain()
        self.assertEqual(
            self._private(endpoint, domain=domain),
            self._public(endpoint, domain=domain),
        )

    def test_private_url_starts_with_https(self):
        """The private URL begins with https://."""
        url = self._private("api/v3.2/user/open_orders")
        self.assertTrue(url.startswith("https://"))

    def test_private_url_contains_endpoint(self):
        """The endpoint path is present in the private URL."""
        endpoint = "api/v3.2/user/wallet"
        url = self._private(endpoint)
        self.assertIn(endpoint, url)


# ---------------------------------------------------------------------------
# Test class 3 — is_exchange_information_valid
# ---------------------------------------------------------------------------

class TestLmexIsExchangeInfoValid(unittest.TestCase):
    """Tests for is_exchange_information_valid predicate."""

    def setUp(self):
        from hummingbot.connector.exchange.lmex.lmex_web_utils import is_exchange_information_valid
        self._fn = is_exchange_information_valid

    def test_active_true_returns_true(self):
        """Returns True when active=True (bool)."""
        self.assertTrue(self._fn({"active": True}))

    def test_active_false_returns_false(self):
        """Returns False when active=False (bool)."""
        self.assertFalse(self._fn({"active": False}))

    def test_missing_active_key_returns_false(self):
        """Returns False when the active key is absent (defaults to False)."""
        self.assertFalse(self._fn({}))

    def test_active_string_true_is_not_valid(self):
        """The string 'true' is not equal to bool True, so the result is False."""
        # The source uses `is True`, not a truthy check
        self.assertFalse(self._fn({"active": "true"}))

    def test_active_integer_one_is_not_valid(self):
        """The integer 1 is truthy but not `is True`, so the result is False."""
        self.assertFalse(self._fn({"active": 1}))

    def test_active_none_returns_false(self):
        """Returns False when active=None."""
        self.assertFalse(self._fn({"active": None}))

    def test_empty_dict_returns_false(self):
        """An empty exchange_info dict returns False."""
        self.assertFalse(self._fn({}))

    def test_extra_fields_ignored(self):
        """Extra keys in exchange_info do not affect the result."""
        self.assertTrue(self._fn({"active": True, "symbol": "BTC-USDT", "base": "BTC"}))


if __name__ == "__main__":
    unittest.main()
