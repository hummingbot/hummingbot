"""Tests for Backpack web utilities."""
import unittest

from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils
from hummingbot.connector.exchange.backpack.backpack_constants import REST_URL, WSS_URL


class TestBackpackWebUtils(unittest.TestCase):
    """Test cases for Backpack web utilities."""

    def test_public_rest_url(self):
        """Test public REST URL construction."""
        path = "/api/v1/markets"
        url = web_utils.public_rest_url(path)
        
        self.assertEqual(url, f"{REST_URL}{path}")

    def test_private_rest_url(self):
        """Test private REST URL construction."""
        path = "/api/v1/order"
        url = web_utils.private_rest_url(path)
        
        self.assertEqual(url, f"{REST_URL}{path}")

    def test_ws_url(self):
        """Test WebSocket URL construction."""
        url = web_utils.ws_url()
        
        self.assertTrue(url.startswith(WSS_URL))


if __name__ == "__main__":
    unittest.main()
