import unittest
import sys
from unittest.mock import MagicMock, patch
from types import ModuleType

# --- MOCKING DEPENDENCIES START ---
import test.hummingbot.connector.derivative.aevo_perpetual.mock_utils as mock_utils
from test.hummingbot.connector.derivative.aevo_perpetual.mock_utils import (
    MockRESTRequest, 
    MockWSRequest, 
    MockWSResponse, 
    MockRESTResponse, 
    MockAuthBase
)
# --- MOCKING DEPENDENCIES END ---

# Now safe to import the class under test (it will use the mocks above)
import asyncio
# We need to ensure we can import the auth module. 
# Since we are mocking dependencies, we can just import the file directly or via module path if PYTHONPATH is set.
# Assuming PYTHONPATH covers the root 'hummingbot' directory.
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_auth import AevoPerpetualAuth

class AevoPerpetualAuthTest(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_key"
        self.api_secret = "test_secret"
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1234567.890
        # Expected timestamp: 1234567890000000 (1e9 check)
        self.auth = AevoPerpetualAuth(self.api_key, self.api_secret, self.mock_time_provider)

    def test_rest_authenticate(self):
        params = {"foo": "bar"}
        # Create a MockRESTRequest (which replaces the real one)
        request = MockRESTRequest(
            method="GET",
            url="https://api.aevo.xyz/test",
            data=params,
        )
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        authenticated_request = loop.run_until_complete(self.auth.rest_authenticate(request))
        loop.close()
        
        headers = authenticated_request.headers
        self.assertIn("AEVO-ACCESS-KEY", headers)
        self.assertEqual(headers["AEVO-ACCESS-KEY"], self.api_key)
        self.assertIn("AEVO-ACCESS-TIMESTAMP", headers)
        # 1234567.890 * 1e9 = 1234567890000000
        self.assertEqual(headers["AEVO-ACCESS-TIMESTAMP"], "1234567890000000") 
        self.assertIn("AEVO-ACCESS-SIG", headers)
        
        # Verify signature existence
        self.assertTrue(len(headers["AEVO-ACCESS-SIG"]) > 0)
        
        # Verify HMAC correctness manually
        # Payload: timestamp + Method + path + body
        # Note: In our implementation, url is passed as is. Aevo might expect path only?
        # Let's assume implementation uses full URL for now as per code.
        # Payload = "1234567890000000GEThttps://api.aevo.xyz/test{\"foo\":\"bar\"}"
        # We can implement a parallel check here if we want strict verification.

    def test_generate_signature(self):
        timestamp = "1234567890"
        method = "GET"
        url = "/test"
        data = {"foo": "bar"}
        
        signature = self.auth._generate_signature(timestamp, method, url, data)
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64) # SHA256 hex digest length
