import asyncio
import hashlib
import hmac
import time
from unittest import TestCase

from hummingbot.connector.exchange.coinmate.coinmate_auth import CoinmateAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


def async_run_with_timeout(coroutine, timeout: float = 1):
        return asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(coroutine, timeout)
        )


class CoinmateAuthTests(TestCase):

    def setUp(self) -> None:
        self.api_key = "testApiKey"
        self.secret_key = "testSecretKey"
        self.client_id = "12345"
        self.auth = CoinmateAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            client_id=self.client_id
        )

    def test_rest_authenticate_get_request(self):
        params = {"currencyPair": "BTC_EUR", "limit": "100"}
        request = RESTRequest(
            method=RESTMethod.GET, params=params, is_auth_required=True
        )
        
        configured_request = async_run_with_timeout(
            self.auth.rest_authenticate(request)
        )
        
        self.assertEqual(configured_request.params["publicKey"], self.api_key)
        self.assertEqual(configured_request.params["clientId"], self.client_id)
        self.assertIn("nonce", configured_request.params)
        self.assertIn("signature", configured_request.params)
        self.assertEqual(configured_request.params["currencyPair"], "BTC_EUR")
        self.assertEqual(configured_request.params["limit"], "100")

    def test_rest_authenticate_post_request(self):
        data = {"currencyPair": "BTC_EUR", "amount": "0.1", "price": "50000"}
        request = RESTRequest(
            method=RESTMethod.POST, data=data, is_auth_required=True
        )
        
        configured_request = async_run_with_timeout(
            self.auth.rest_authenticate(request)
        )
        
        # Should be URL-encoded
        self.assertIsInstance(configured_request.data, str)
        self.assertIn("publicKey=" + self.api_key, configured_request.data)
        self.assertIn("clientId=" + self.client_id, configured_request.data)
        self.assertIn("nonce=", configured_request.data)
        self.assertIn("signature=", configured_request.data)

    def test_signature_calculation_matches_spec(self):
        """Test signature matches Coinmate API specification:
        HMAC-SHA256(nonce + clientId + publicKey, privateKey)
        """
        test_nonce = "1234567890000"
        
        generated_signature = self.auth._generate_signature(test_nonce)
        
        # Calculate expected signature per Coinmate spec
        message = f"{test_nonce}{self.client_id}{self.api_key}"
        expected_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()
        
        self.assertEqual(generated_signature, expected_signature)
        self.assertEqual(len(generated_signature), 64)
        self.assertTrue(generated_signature.isupper())

    def test_nonce_increases(self):
        """Test nonce values increase over time"""
        nonce1 = int(self.auth._generate_nonce())
        time.sleep(0.001)
        nonce2 = int(self.auth._generate_nonce())
        
        self.assertGreater(nonce2, nonce1)
        
        current_ms = int(time.time() * 1000)
        self.assertLess(abs(nonce1 - current_ms), 60000)

    def test_ws_auth_data(self):
        """Test WebSocket authentication data generation"""
        auth_data = self.auth.get_ws_auth_data()
        
        self.assertEqual(auth_data["clientId"], self.client_id)
        self.assertEqual(auth_data["publicKey"], self.api_key)
        self.assertIn("nonce", auth_data)
        self.assertIn("signature", auth_data)
        self.assertTrue(auth_data["nonce"].isdigit())
        self.assertEqual(len(auth_data["signature"]), 64)