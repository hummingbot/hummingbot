import base64
import unittest
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS
from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class TestBackpackAuth(unittest.TestCase):
    """Test suite for Backpack authentication."""

    @classmethod
    def setUpClass(cls):
        # Generate a real ED25519 key pair for testing
        cls.private_key = Ed25519PrivateKey.generate()
        cls.public_key = cls.private_key.public_key()

        # Get raw bytes
        from cryptography.hazmat.primitives import serialization
        private_bytes = cls.private_key.private_bytes_raw()
        public_bytes = cls.public_key.public_bytes_raw()

        # Base64 encode for Backpack format
        cls.api_key = base64.b64encode(public_bytes).decode("utf-8")
        cls.api_secret = base64.b64encode(private_bytes).decode("utf-8")

    def test_auth_initialization_base64_key(self):
        """Test auth initialization with base64-encoded key."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)
        self.assertEqual(auth._api_key, self.api_key)
        self.assertIsNotNone(auth._private_key)

    def test_auth_initialization_hex_key(self):
        """Test auth initialization with hex-encoded key."""
        # Convert private key to hex
        private_bytes = self.private_key.private_bytes_raw()
        hex_secret = private_bytes.hex()

        auth = BackpackAuth(api_key=self.api_key, api_secret=hex_secret)
        self.assertIsNotNone(auth._private_key)

    def test_auth_initialization_invalid_key(self):
        """Test auth initialization fails with invalid key."""
        with self.assertRaises(ValueError) as context:
            BackpackAuth(api_key=self.api_key, api_secret="invalid_key")

        self.assertIn("Unable to load ED25519 private key", str(context.exception))

    def test_sign_message(self):
        """Test message signing produces valid signature."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

        message = "test_message_to_sign"
        signature = auth._sign_message(message)

        # Verify signature is base64 encoded
        decoded = base64.b64decode(signature)
        self.assertEqual(len(decoded), 64)  # ED25519 signatures are 64 bytes

        # Verify the signature is valid
        message_bytes = message.encode("utf-8")
        try:
            self.public_key.verify(decoded, message_bytes)
        except Exception as e:
            self.fail(f"Signature verification failed: {e}")

    def test_build_signing_string_basic(self):
        """Test building signing string with basic parameters."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

        timestamp = 1234567890000
        window = 5000

        signing_string = auth._build_signing_string(
            instruction="orderExecute",
            params=None,
            timestamp=timestamp,
            window=window,
        )

        expected = "instruction=orderExecute&timestamp=1234567890000&window=5000"
        self.assertEqual(expected, signing_string)

    def test_build_signing_string_with_params(self):
        """Test building signing string with sorted parameters."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

        timestamp = 1234567890000
        window = 5000

        params = {
            "symbol": "BTC_USDC",
            "side": "Bid",
            "orderType": "Limit",
            "quantity": "1.0",
            "price": "50000.00",
            "clientId": "test123",
        }

        signing_string = auth._build_signing_string(
            instruction="orderExecute",
            params=params,
            timestamp=timestamp,
            window=window,
        )

        # Parameters should be alphabetically sorted
        self.assertIn("instruction=orderExecute", signing_string)
        self.assertIn("clientId=test123", signing_string)
        self.assertIn("orderType=Limit", signing_string)
        self.assertIn("price=50000.00", signing_string)
        self.assertIn("quantity=1.0", signing_string)
        self.assertIn("side=Bid", signing_string)
        self.assertIn("symbol=BTC_USDC", signing_string)
        self.assertIn("timestamp=1234567890000", signing_string)
        self.assertIn("window=5000", signing_string)

        # Verify alphabetical order
        parts = signing_string.split("&")
        keys = [p.split("=")[0] for p in parts]
        # instruction should be first, then params alphabetically, then timestamp, window
        self.assertEqual(keys[0], "instruction")
        self.assertEqual(keys[-2], "timestamp")
        self.assertEqual(keys[-1], "window")

    def test_build_signing_string_with_boolean(self):
        """Test building signing string handles booleans correctly."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

        timestamp = 1234567890000
        window = 5000

        params = {
            "symbol": "BTC_USDC",
            "postOnly": True,
        }

        signing_string = auth._build_signing_string(
            instruction="orderExecute",
            params=params,
            timestamp=timestamp,
            window=window,
        )

        self.assertIn("postOnly=true", signing_string)

    def test_generate_auth_headers(self):
        """Test generating authentication headers."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

        timestamp = 1234567890000
        window = 5000

        headers = auth.generate_auth_headers(
            instruction="balanceQuery",
            params=None,
            timestamp=timestamp,
            window=window,
        )

        self.assertIn("X-API-Key", headers)
        self.assertIn("X-Signature", headers)
        self.assertIn("X-Timestamp", headers)
        self.assertIn("X-Window", headers)

        self.assertEqual(headers["X-API-Key"], self.api_key)
        self.assertEqual(headers["X-Timestamp"], str(timestamp))
        self.assertEqual(headers["X-Window"], str(window))

        # Verify signature is valid base64
        signature = headers["X-Signature"]
        decoded = base64.b64decode(signature)
        self.assertEqual(len(decoded), 64)

    def test_generate_ws_auth_payload(self):
        """Test generating WebSocket authentication payload."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

        with patch.object(auth, "_get_timestamp", return_value=1234567890000):
            payload = auth.generate_ws_auth_payload(streams=["account.orderUpdate"])

        self.assertEqual(payload["method"], "SUBSCRIBE")
        self.assertEqual(payload["params"], ["account.orderUpdate"])
        self.assertIn("signature", payload)

        # Signature should be [api_key, signature, timestamp, window]
        sig_array = payload["signature"]
        self.assertEqual(len(sig_array), 4)
        self.assertEqual(sig_array[0], self.api_key)
        self.assertEqual(sig_array[2], "1234567890000")
        self.assertEqual(sig_array[3], str(CONSTANTS.DEFAULT_WINDOW))

    def test_generate_ws_unsubscribe_payload(self):
        """Test generating WebSocket unsubscribe payload."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

        payload = auth.generate_ws_unsubscribe_payload(streams=["account.orderUpdate"])

        self.assertEqual(payload["method"], "UNSUBSCRIBE")
        self.assertEqual(payload["params"], ["account.orderUpdate"])
        self.assertNotIn("signature", payload)

    def test_infer_instruction_order_execute(self):
        """Test instruction inference for order execution."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

        instruction = auth._infer_instruction(
            method=RESTMethod.POST,
            url="https://api.backpack.exchange/api/v1/order",
            params={"symbol": "BTC_USDC"},
        )

        self.assertEqual(instruction, CONSTANTS.INSTRUCTION_ORDER_EXECUTE)

    def test_infer_instruction_order_cancel(self):
        """Test instruction inference for order cancellation."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

        instruction = auth._infer_instruction(
            method=RESTMethod.DELETE,
            url="https://api.backpack.exchange/api/v1/order",
            params={"orderId": "12345"},
        )

        self.assertEqual(instruction, CONSTANTS.INSTRUCTION_ORDER_CANCEL)

    def test_infer_instruction_balance_query(self):
        """Test instruction inference for balance query."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

        instruction = auth._infer_instruction(
            method=RESTMethod.GET,
            url="https://api.backpack.exchange/api/v1/capital",
            params=None,
        )

        self.assertEqual(instruction, CONSTANTS.INSTRUCTION_BALANCE_QUERY)

    def test_infer_instruction_order_query(self):
        """Test instruction inference for order query."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

        instruction = auth._infer_instruction(
            method=RESTMethod.GET,
            url="https://api.backpack.exchange/api/v1/order",
            params={"orderId": "12345"},
        )

        self.assertEqual(instruction, CONSTANTS.INSTRUCTION_ORDER_QUERY)

    def test_infer_instruction_order_query_all(self):
        """Test instruction inference for querying all orders."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

        instruction = auth._infer_instruction(
            method=RESTMethod.GET,
            url="https://api.backpack.exchange/api/v1/order",
            params={"symbol": "BTC_USDC"},
        )

        self.assertEqual(instruction, CONSTANTS.INSTRUCTION_ORDER_QUERY_ALL)

    def test_get_timestamp(self):
        """Test timestamp generation."""
        auth = BackpackAuth(api_key=self.api_key, api_secret=self.api_secret)

        timestamp = auth._get_timestamp()

        # Should be a valid timestamp in milliseconds
        self.assertIsInstance(timestamp, int)
        self.assertGreater(timestamp, 1600000000000)  # After 2020

    def test_load_private_key_64_byte_format(self):
        """Test loading private key from 64-byte format (private + public)."""
        # Some tools export keys as 64 bytes (32 private + 32 public)
        private_bytes = self.private_key.private_bytes_raw()
        public_bytes = self.public_key.public_bytes_raw()
        combined = private_bytes + public_bytes

        combined_b64 = base64.b64encode(combined).decode("utf-8")

        auth = BackpackAuth(api_key=self.api_key, api_secret=combined_b64)
        self.assertIsNotNone(auth._private_key)


if __name__ == "__main__":
    unittest.main()
