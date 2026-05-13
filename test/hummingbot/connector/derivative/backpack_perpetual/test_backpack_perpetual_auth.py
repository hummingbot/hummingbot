import base64
import json
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_auth import BackpackPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class BackpackPerpetualAuthTests(IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        # --- generate deterministic test keypair ---
        # NOTE: testSecret / testKey are VARIABLE NAMES, not literal values
        testSecret = ed25519.Ed25519PrivateKey.generate()
        testKey = testSecret.public_key()

        # --- extract raw key bytes ---
        seed_bytes = testSecret.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )  # 32 bytes

        public_key_bytes = testKey.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )  # 32 bytes

        # --- Backpack expects BASE64 ---
        self._secret = base64.b64encode(seed_bytes).decode("utf-8")
        self._api_key = base64.b64encode(public_key_bytes).decode("utf-8")

        # keep reference if you want to sign/verify manually in tests
        self._private_key = testSecret
        self._public_key = testKey

        # --- time provider ---
        self.now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = self.now

        # --- auth under test ---
        self._auth = BackpackPerpetualAuth(
            api_key=self._api_key,
            secret_key=self._secret,
            time_provider=mock_time_provider,
        )

    async def test_rest_authenticate_get_request(self):
        params = {
            "symbol": "SOL_USDC",
            "limit": 100,
        }

        request = RESTRequest(method=RESTMethod.GET, params=params, is_auth_required=True)
        configured_request = await self._auth.rest_authenticate(request)

        # Verify headers are set correctly
        self.assertEqual(str(int(self.now * 1e3)), configured_request.headers["X-Timestamp"])
        self.assertEqual(str(self._auth.DEFAULT_WINDOW_MS), configured_request.headers["X-Window"])
        self.assertEqual(self._api_key, configured_request.headers["X-API-Key"])
        self.assertIn("X-Signature", configured_request.headers)

        # Verify signature
        sign_str = f"limit={params['limit']}&symbol={params['symbol']}&timestamp={int(self.now * 1e3)}&window={self._auth.DEFAULT_WINDOW_MS}"
        expected_signature_bytes = self._private_key.sign(sign_str.encode("utf-8"))
        expected_signature = base64.b64encode(expected_signature_bytes).decode("utf-8")

        self.assertEqual(expected_signature, configured_request.headers["X-Signature"])

        # Verify params unchanged
        self.assertEqual(params, configured_request.params)

    async def test_rest_authenticate_post_request_with_body(self):
        body_data = {
            "orderType": "Limit",
            "side": "Bid",
            "symbol": "SOL_USDC",
            "quantity": "10",
            "price": "100.5",
        }
        request = RESTRequest(
            method=RESTMethod.POST,
            data=json.dumps(body_data),
            is_auth_required=True
        )
        configured_request = await self._auth.rest_authenticate(request)

        # Verify headers are set correctly
        self.assertEqual(str(int(self.now * 1e3)), configured_request.headers["X-Timestamp"])
        self.assertEqual(str(self._auth.DEFAULT_WINDOW_MS), configured_request.headers["X-Window"])
        self.assertEqual(self._api_key, configured_request.headers["X-API-Key"])
        self.assertIn("X-Signature", configured_request.headers)

        # Verify signature (signs body params in sorted order)
        sign_str = (f"orderType={body_data['orderType']}&price={body_data['price']}&quantity={body_data['quantity']}&"
                    f"side={body_data['side']}&symbol={body_data['symbol']}&timestamp={int(self.now * 1e3)}&"
                    f"window={self._auth.DEFAULT_WINDOW_MS}")
        expected_signature_bytes = self._private_key.sign(sign_str.encode("utf-8"))
        expected_signature = base64.b64encode(expected_signature_bytes).decode("utf-8")

        self.assertEqual(expected_signature, configured_request.headers["X-Signature"])

        # Verify body unchanged
        self.assertEqual(json.dumps(body_data), configured_request.data)

    async def test_rest_authenticate_with_instruction(self):
        body_data = {
            "symbol": "SOL_USDC",
            "side": "Bid",
        }

        request = RESTRequest(
            method=RESTMethod.POST,
            data=json.dumps(body_data),
            headers={"instruction": "orderQueryAll"},
            is_auth_required=True
        )
        configured_request = await self._auth.rest_authenticate(request)

        # Verify instruction header is removed
        self.assertNotIn("instruction", configured_request.headers)

        # Verify signature includes instruction
        sign_str = (f"instruction=orderQueryAll&side={body_data['side']}&symbol={body_data['symbol']}&"
                    f"timestamp={int(self.now * 1e3)}&window={self._auth.DEFAULT_WINDOW_MS}")
        expected_signature_bytes = self._private_key.sign(sign_str.encode("utf-8"))
        expected_signature = base64.b64encode(expected_signature_bytes).decode("utf-8")

        self.assertEqual(expected_signature, configured_request.headers["X-Signature"])

    async def test_rest_authenticate_empty_params(self):
        request = RESTRequest(method=RESTMethod.GET, is_auth_required=True)
        configured_request = await self._auth.rest_authenticate(request)

        # Verify signature with only timestamp and window
        sign_str = f"timestamp={int(self.now * 1e3)}&window={self._auth.DEFAULT_WINDOW_MS}"
        expected_signature_bytes = self._private_key.sign(sign_str.encode("utf-8"))
        expected_signature = base64.b64encode(expected_signature_bytes).decode("utf-8")

        self.assertEqual(expected_signature, configured_request.headers["X-Signature"])
