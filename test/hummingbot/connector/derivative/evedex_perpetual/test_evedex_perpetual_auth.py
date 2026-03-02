import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth import EvedexPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class EvedexPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "0x1234567890abcdef1234567890abcdef12345678"
        self.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        self.use_api_key_auth = False
        
        self.auth = EvedexPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            use_api_key_auth=self.use_api_key_auth
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _get_timestamp(self):
        return 1678974447.926

    def test_wallet_address_property(self):
        """Test that wallet address is correctly derived from private key."""
        self.assertIsNotNone(self.auth.wallet_address)
        self.assertTrue(self.auth.wallet_address.startswith("0x"))

    def test_get_eip712_domain_mainnet(self):
        """Test EIP-712 domain for mainnet."""
        domain = self.auth.get_eip712_domain(is_mainnet=True)
        
        self.assertEqual(domain["name"], "EVEDEX")
        self.assertEqual(domain["version"], "1")
        self.assertEqual(domain["chainId"], 1)

    def test_get_eip712_domain_testnet(self):
        """Test EIP-712 domain for testnet."""
        domain = self.auth.get_eip712_domain(is_mainnet=False)
        
        self.assertEqual(domain["name"], "EVEDEX")
        self.assertEqual(domain["version"], "1")
        self.assertEqual(domain["chainId"], 5)

    def test_get_order_types(self):
        """Test that order types include required EIP-712 types."""
        types = self.auth.get_order_types()
        
        self.assertIn("EIP712Domain", types)
        self.assertIn("Order", types)
        self.assertIn("CancelOrder", types)

    @patch(
        "hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth.EvedexPerpetualAuth._get_timestamp")
    def test_sign_order(self, ts_mock: MagicMock):
        """Test order signing with EIP-712."""
        timestamp = self._get_timestamp()
        ts_mock.return_value = timestamp
        
        signed_order = self.auth.sign_order(
            instrument="BTCUSDT",
            side="buy",
            price="50000",
            quantity="0.1",
            order_type="limit",
            time_in_force="GTC",
            client_order_id="test_order_123",
            is_mainnet=True
        )
        
        self.assertEqual(signed_order["instrument"], "BTCUSDT")
        self.assertEqual(signed_order["side"], "buy")
        self.assertEqual(signed_order["price"], "50000")
        self.assertEqual(signed_order["quantity"], "0.1")
        self.assertIn("signature", signed_order)
        self.assertIn("r", signed_order["signature"])
        self.assertIn("s", signed_order["signature"])
        self.assertIn("v", signed_order["signature"])

    @patch(
        "hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth.EvedexPerpetualAuth._get_timestamp")
    def test_sign_cancel_order(self, ts_mock: MagicMock):
        """Test cancel order signing with EIP-712."""
        timestamp = self._get_timestamp()
        ts_mock.return_value = timestamp
        
        signed_cancel = self.auth.sign_cancel_order(
            order_id="order_12345",
            instrument="BTCUSDT",
            is_mainnet=True
        )
        
        self.assertEqual(signed_cancel["orderId"], "order_12345")
        self.assertEqual(signed_cancel["instrument"], "BTCUSDT")
        self.assertIn("signature", signed_cancel)

    def test_add_auth_headers_wallet_mode(self):
        """Test adding auth headers in wallet mode."""
        headers = {}
        result = self.auth.add_auth_headers(headers)
        
        self.assertIn("X-Wallet-Address", result)
        self.assertEqual(result["X-Wallet-Address"], self.auth.wallet_address)

    def test_add_auth_headers_api_key_mode(self):
        """Test adding auth headers in API key mode."""
        api_key_auth = EvedexPerpetualAuth(
            api_key="test_api_key",
            api_secret="test_api_secret",
            use_api_key_auth=True
        )
        
        headers = {}
        result = api_key_auth.add_auth_headers(headers)
        
        self.assertIn("X-API-Key", result)
        self.assertIn("X-Timestamp", result)
        self.assertIn("X-Signature", result)

    def test_rest_authenticate(self):
        """Test REST request authentication."""
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/api/v1/private/order",
            data=json.dumps({"test": "data"}),
            is_auth_required=True,
        )
        
        authenticated_request = self.async_run_with_timeout(self.auth.rest_authenticate(request))
        
        self.assertIsNotNone(authenticated_request.headers)
        self.assertIn("X-Wallet-Address", authenticated_request.headers)

    def test_get_ws_auth_payload_wallet_mode(self):
        """Test WebSocket auth payload generation in wallet mode."""
        payload = self.auth.get_ws_auth_payload()
        
        self.assertIn("walletAddress", payload)
        self.assertIn("timestamp", payload)
        self.assertIn("signature", payload)

    def test_get_ws_auth_payload_api_key_mode(self):
        """Test WebSocket auth payload generation in API key mode."""
        api_key_auth = EvedexPerpetualAuth(
            api_key="test_api_key",
            api_secret="test_api_secret",
            use_api_key_auth=True
        )
        
        payload = api_key_auth.get_ws_auth_payload()
        
        self.assertIn("apiKey", payload)
        self.assertIn("timestamp", payload)
        self.assertIn("signature", payload)

    def test_sign_typed_data_api_key_mode_raises(self):
        """Test that signing in API key mode raises an error."""
        api_key_auth = EvedexPerpetualAuth(
            api_key="test_api_key",
            api_secret="test_api_secret",
            use_api_key_auth=True
        )
        
        with self.assertRaises(ValueError) as context:
            api_key_auth.sign_typed_data({})
        
        self.assertIn("Cannot sign with API key authentication mode", str(context.exception))
