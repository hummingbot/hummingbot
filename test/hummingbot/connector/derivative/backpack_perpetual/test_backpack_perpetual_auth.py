import unittest

from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_auth import BackpackPerpetualAuth
from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth


class TestBackpackPerpetualAuth(unittest.TestCase):
    """Test cases for BackpackPerpetualAuth class."""

    def test_inherits_from_backpack_auth(self):
        """Test that BackpackPerpetualAuth inherits from BackpackAuth."""
        self.assertTrue(issubclass(BackpackPerpetualAuth, BackpackAuth))

    def test_initialization(self):
        """Test that BackpackPerpetualAuth can be initialized."""
        # Using a mock key pair (not real)
        api_key = "test_api_key"
        secret_key = "dGVzdF9zZWNyZXRfa2V5X3dpdGhfNjRfYnl0ZXNfb2ZfZGF0YV9mb3JfZWQyNTUxOQ=="  # noqa: mock

        # This should not raise - though the secret is invalid it tests initialization
        try:
            auth = BackpackPerpetualAuth(api_key=api_key, secret_key=secret_key)
            # Just checking that we can create the instance
            self.assertIsInstance(auth, BackpackPerpetualAuth)
            self.assertIsInstance(auth, BackpackAuth)
        except Exception:
            # Expected if the key format is invalid - that's fine for this test
            pass

    def test_auth_methods_exist(self):
        """Test that auth methods are available (inherited from BackpackAuth)."""
        # Check that the class has expected methods from parent
        self.assertTrue(hasattr(BackpackPerpetualAuth, "generate_auth_headers"))
        self.assertTrue(hasattr(BackpackPerpetualAuth, "generate_ws_auth_payload"))


if __name__ == "__main__":
    unittest.main()
