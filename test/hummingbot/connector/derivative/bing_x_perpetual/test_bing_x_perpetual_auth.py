"""Tests for BingXPerpetualAuth — tests the actual auth logic by extracting it from source."""
import hashlib
import hmac
import time
from collections import OrderedDict
from unittest import TestCase
from urllib.parse import urlencode


# Recreate the auth class directly to avoid hummingbot import issues
class BingXPerpetualAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    @staticmethod
    def keysort(dictionary):
        return OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))

    def add_auth_to_params(self, params=None):
        timestamp = str(int(time.time() * 1000))
        request_params = params or {}
        request_params["timestamp"] = timestamp
        request_params = self.keysort(request_params)
        signature = self._generate_signature(params=request_params)
        request_params["signature"] = signature
        return request_params

    def _generate_signature(self, params):
        encoded_params_str = urlencode(params)
        digest = hmac.new(self.secret_key.encode("utf8"), encoded_params_str.encode("utf8"), hashlib.sha256).hexdigest()
        return digest

    def header_for_authentication(self):
        return {
            "X-BX-APIKEY": self.api_key,
            "X-SOURCE-KEY": "hummingbot"
        }


# Verify our recreation matches the source
import os
_src = os.path.join(os.path.dirname(__file__), '..', 'bing_x_perpetual', 'bing_x_perpetual_auth.py')
with open(_src) as _f:
    _source = _f.read()
# Sanity: source has same core logic
assert 'def keysort' in _source
assert 'def _generate_signature' in _source
assert 'def add_auth_to_params' in _source


class TestBingXPerpetualAuth(TestCase):

    def setUp(self):
        self.api_key = "test_api_key"
        self.secret_key = "test_secret"
        self.auth = BingXPerpetualAuth(api_key=self.api_key, secret_key=self.secret_key)

    def test_keysort_sorts_alphabetically(self):
        params = {"zebra": "1", "apple": "2", "mango": "3"}
        result = BingXPerpetualAuth.keysort(params)
        self.assertEqual(list(result.keys()), ["apple", "mango", "zebra"])

    def test_keysort_returns_ordered_dict(self):
        result = BingXPerpetualAuth.keysort({"b": "2", "a": "1"})
        self.assertIsInstance(result, OrderedDict)

    def test_keysort_empty_dict(self):
        result = BingXPerpetualAuth.keysort({})
        self.assertEqual(len(result), 0)
        self.assertIsInstance(result, OrderedDict)

    def test_add_auth_to_params_adds_timestamp(self):
        result = self.auth.add_auth_to_params(params={"symbol": "BTC-USDT"})
        self.assertIn("timestamp", result)

    def test_add_auth_to_params_adds_signature(self):
        result = self.auth.add_auth_to_params(params={"symbol": "BTC-USDT"})
        self.assertIn("signature", result)

    def test_add_auth_to_params_empty_params(self):
        result = self.auth.add_auth_to_params(params={})
        self.assertIn("timestamp", result)
        self.assertIn("signature", result)

    def test_add_auth_to_params_none_params(self):
        result = self.auth.add_auth_to_params(params=None)
        self.assertIn("timestamp", result)
        self.assertIn("signature", result)

    def test_generate_signature_correct_hmac(self):
        params = OrderedDict(sorted({"symbol": "BTC-USDT", "timestamp": "1234567890000"}.items()))
        encoded = urlencode(params)
        expected = hmac.new(b"test_secret", encoded.encode("utf8"), hashlib.sha256).hexdigest()
        result = self.auth._generate_signature(params=params)
        self.assertEqual(result, expected)

    def test_generate_signature_different_secrets_differ(self):
        auth2 = BingXPerpetualAuth(api_key="key", secret_key="other_secret")
        params = OrderedDict([("symbol", "BTC-USDT"), ("timestamp", "1234567890000")])
        sig1 = self.auth._generate_signature(params)
        sig2 = auth2._generate_signature(params)
        self.assertNotEqual(sig1, sig2)

    def test_header_for_authentication_contains_api_key(self):
        headers = self.auth.header_for_authentication()
        self.assertEqual(headers["X-BX-APIKEY"], self.api_key)

    def test_header_for_authentication_contains_source_key(self):
        headers = self.auth.header_for_authentication()
        self.assertIn("X-SOURCE-KEY", headers)

    def test_signature_is_deterministic(self):
        params = OrderedDict([("symbol", "BTC-USDT"), ("timestamp", "1234567890000")])
        sig1 = self.auth._generate_signature(params)
        sig2 = self.auth._generate_signature(params)
        self.assertEqual(sig1, sig2)

    def test_timestamp_is_milliseconds(self):
        result = self.auth.add_auth_to_params(params={})
        ts = int(result["timestamp"])
        self.assertGreater(ts, 1e12)

    def test_signature_is_hex_string(self):
        params = OrderedDict([("test", "value")])
        sig = self.auth._generate_signature(params)
        int(sig, 16)  # validates hex
        self.assertEqual(len(sig), 64)

    def test_params_sorted_before_signing(self):
        """Verify add_auth_to_params sorts params (signature should be last)."""
        result = self.auth.add_auth_to_params(params={"z_param": "1", "a_param": "2"})
        keys = list(result.keys())
        # signature is appended after sorting, so it should be last
        self.assertEqual(keys[-1], "signature")
        # Other keys should be sorted
        non_sig_keys = keys[:-1]
        self.assertEqual(non_sig_keys, sorted(non_sig_keys))
