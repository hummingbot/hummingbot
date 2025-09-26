import asyncio
import hashlib
import hmac
import time
from copy import copy
from unittest import TestCase

from typing_extensions import Awaitable

from hummingbot.connector.exchange.coinmate.coinmate_auth import CoinmateAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class CoinmateAuthTests(TestCase):

    def setUp(self) -> None:
        self._api_key = "test_api_key"
        self._secret_key = "test_secret_key"
        self._client_id = "test_client_id"

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(
            asyncio.wait_for(coroutine, timeout)
        )
        return ret

    def test_rest_authenticate_get_request(self):
        """Test REST authentication for GET requests"""        
        params = {
            "currencyPair": "BTC_EUR",
            "limit": "100"
        }
        full_params = copy(params)
        
        auth = CoinmateAuth(
            api_key=self._api_key, 
            secret_key=self._secret_key, 
            client_id=self._client_id
        )
        
        request = RESTRequest(
            method=RESTMethod.GET, params=params, is_auth_required=True
        )
        configured_request = self.async_run_with_timeout(
            auth.rest_authenticate(request)
        )
        
        # Verify authentication parameters were added
        self.assertEqual(configured_request.params["publicKey"], self._api_key)
        self.assertEqual(configured_request.params["clientId"], self._client_id)
        self.assertIn("nonce", configured_request.params)
        self.assertIn("signature", configured_request.params)
        
        # Verify original params are preserved
        for key, value in full_params.items():
            self.assertEqual(configured_request.params[key], value)
        
        # Verify nonce format (should be numeric string representing milliseconds)
        nonce = configured_request.params["nonce"]
        self.assertTrue(nonce.isdigit())
        self.assertGreater(int(nonce), 1000000000000)  # Should be in milliseconds
        
        # Verify signature format
        signature = configured_request.params["signature"]
        self.assertTrue(signature.isupper())  # Should be uppercase hex
        self.assertEqual(len(signature), 64)  # SHA256 hex string length

    def test_rest_authenticate_post_request(self):
        """Test REST authentication for POST requests"""
        data = {
            "currencyPair": "BTC_EUR", 
            "amount": "0.1",
            "price": "50000"
        }
        full_data = copy(data)
        
        auth = CoinmateAuth(
            api_key=self._api_key, 
            secret_key=self._secret_key, 
            client_id=self._client_id
        )
        
        request = RESTRequest(
            method=RESTMethod.POST, data=data, is_auth_required=True
        )
        configured_request = self.async_run_with_timeout(
            auth.rest_authenticate(request)
        )
        
        # Verify authentication parameters were added to data
        self.assertEqual(configured_request.data["publicKey"], self._api_key)
        self.assertEqual(configured_request.data["clientId"], self._client_id)
        self.assertIn("nonce", configured_request.data)
        self.assertIn("signature", configured_request.data)
        
        # Verify original data is preserved
        for key, value in full_data.items():
            self.assertEqual(configured_request.data[key], value)
            
        # Verify nonce format (should be numeric string representing milliseconds)
        nonce = configured_request.data["nonce"]
        self.assertTrue(nonce.isdigit())
        self.assertGreater(int(nonce), 1000000000000)  # Should be in milliseconds
        
        # Verify signature format
        signature = configured_request.data["signature"]
        self.assertTrue(signature.isupper())  # Should be uppercase hex
        self.assertEqual(len(signature), 64)  # SHA256 hex string length

    def test_signature_calculation_matches_coinmate_spec(self):
        """Test signature calculation matches Coinmate API specification exactly"""
        # Test with specific values to verify exact signature calculation
        test_nonce = "1234567890000"  # Fixed nonce for deterministic test
        test_api_key = "testPublicKey123"
        test_secret_key = "testPrivateKey456"
        test_client_id = "12345"
        
        auth = CoinmateAuth(
            api_key=test_api_key,
            secret_key=test_secret_key,
            client_id=test_client_id
        )
        
        # Calculate signature using our implementation
        generated_signature = auth._generate_signature(test_nonce)
        
        # Calculate expected signature using Coinmate's specification:
        # signatureInput = nonce + clientId + publicApiKey
        
        message = f"{test_nonce}{test_client_id}{test_api_key}"
        expected_signature = hmac.new(
            test_secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()
        
        # Verify our implementation matches the specification exactly
        self.assertEqual(generated_signature, expected_signature)
        self.assertEqual(len(generated_signature), 64)
        self.assertTrue(generated_signature.isupper())
        
        # Verify message construction order: nonce + clientId + publicKey
        self.assertEqual(message, f"{test_nonce}{test_client_id}{test_api_key}")
        
    def test_nonce_is_increasing_timestamp(self):
        """Test that nonce values represent current timestamps and increase"""
        auth = CoinmateAuth(
            api_key=self._api_key,
            secret_key=self._secret_key,
            client_id=self._client_id
        )
        
        # Get two authentication requests with small delay
        
        request1 = RESTRequest(
            method=RESTMethod.GET, params={}, is_auth_required=True
        )
        configured_request1 = self.async_run_with_timeout(
            auth.rest_authenticate(request1)
        )
        
        time.sleep(0.001)  # Small delay to ensure different timestamps
        
        request2 = RESTRequest(
            method=RESTMethod.GET, params={}, is_auth_required=True
        )
        configured_request2 = self.async_run_with_timeout(
            auth.rest_authenticate(request2)
        )
        
        nonce1 = int(configured_request1.params["nonce"])
        nonce2 = int(configured_request2.params["nonce"])
        
        # Nonce should be increasing (second should be >= first)
        self.assertGreaterEqual(nonce2, nonce1)
        
        # Nonces should be in milliseconds range (roughly current time)
        current_time_ms = int(time.time() * 1000)
        self.assertGreater(nonce1, current_time_ms - 60000)  # Within last minute
        self.assertLess(nonce1, current_time_ms + 60000)     # Within next minute
