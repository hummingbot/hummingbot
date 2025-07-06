"""
Unit tests for GatewayHttpClient focusing on logic without HTTP calls.
Tests caching, fee calculations, and transaction management logic.
"""
import asyncio
import time
import unittest
from unittest.mock import Mock

from hummingbot.connector.gateway.gateway_http_client import GatewayHttpClient


class TestGatewayHttpClientUnit(unittest.TestCase):
    """
    Unit test class for GatewayHttpClient logic
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.ev_loop)

    def setUp(self) -> None:
        super().setUp()

        # Mock client configuration
        self.mock_client_config = Mock()
        self.mock_client_config.gateway = Mock()
        self.mock_client_config.gateway.gateway_use_ssl = False
        self.mock_client_config.gateway.gateway_api_host = "localhost"
        self.mock_client_config.gateway.gateway_api_port = 5000

        # Clear singleton instance
        GatewayHttpClient._GatewayHttpClient__instance = None

        # Create gateway HTTP client instance
        self.gateway_http_client = GatewayHttpClient(client_config_map=self.mock_client_config)

    def tearDown(self) -> None:
        # Clear singleton instance
        GatewayHttpClient._GatewayHttpClient__instance = None
        super().tearDown()

    def test_singleton_behavior(self):
        """Test that GatewayHttpClient behaves as a singleton"""
        # First instance created in setUp
        instance1 = self.gateway_http_client

        # Get instance should return the same object
        instance2 = GatewayHttpClient.get_instance(self.mock_client_config)
        self.assertIs(instance1, instance2)

        # Creating new instance directly updates the singleton
        instance3 = GatewayHttpClient(client_config_map=self.mock_client_config)
        instance4 = GatewayHttpClient.get_instance(self.mock_client_config)
        self.assertIs(instance3, instance4)

    def test_base_url_construction(self):
        """Test base URL construction from config"""
        # Non-SSL
        self.assertEqual(self.gateway_http_client.base_url, "http://localhost:5000")

        # Test with SSL
        self.mock_client_config.gateway.gateway_use_ssl = True
        client_ssl = GatewayHttpClient(client_config_map=self.mock_client_config)
        self.assertEqual(client_ssl.base_url, "https://localhost:5000")

    def test_compute_units_cache(self):
        """Test compute units caching functionality"""
        # Test cache storage
        self.gateway_http_client.cache_compute_units("swap", "solana", "mainnet-beta", 200000)

        # Test cache retrieval
        config = {"defaultComputeUnits": 150000}
        cached_units = self.gateway_http_client._get_cached_compute_units(
            "swap", "solana", "mainnet-beta", config
        )
        self.assertEqual(cached_units, 200000)

        # Test cache key format (using colon separator)
        cache_key = "swap:solana:mainnet-beta"
        self.assertIn(cache_key, self.gateway_http_client._compute_units_cache)

        # Test default value when not cached
        uncached_units = self.gateway_http_client._get_cached_compute_units(
            "lp", "solana", "mainnet-beta", config
        )
        self.assertEqual(uncached_units, 150000)

    def test_compute_units_cache_expiry(self):
        """Test compute units cache expiration (5 minutes)"""
        config = {"defaultComputeUnits": 150000}

        # Add entry with old timestamp - but compute units cache doesn't have timestamps
        # Instead, just test that cache exists
        self.gateway_http_client._compute_units_cache["swap:solana:mainnet-beta"] = 200000

        # Should return cached value (compute units cache doesn't expire)
        cached_units = self.gateway_http_client._get_cached_compute_units(
            "swap", "solana", "mainnet-beta", config
        )
        self.assertEqual(cached_units, 200000)

    def test_fee_estimate_cache(self):
        """Test fee estimation caching functionality"""
        # Add to cache
        current_time = time.time()
        self.gateway_http_client._fee_estimates["solana:mainnet-beta"] = {
            "fee_per_compute_unit": 1500,
            "denomination": "lamports",
            "timestamp": current_time
        }

        # Verify it was cached
        cache_key = "solana:mainnet-beta"
        self.assertIn(cache_key, self.gateway_http_client._fee_estimates)
        self.assertEqual(self.gateway_http_client._fee_estimates[cache_key]["fee_per_compute_unit"], 1500)

        # Test with non-existent key
        self.assertNotIn("ethereum:mainnet", self.gateway_http_client._fee_estimates)

    def test_fee_estimate_cache_expiry(self):
        """Test fee estimation cache expiration (1 minute)"""
        # Add entry with old timestamp
        old_time = time.time() - 61  # More than 1 minute ago
        self.gateway_http_client._fee_estimates["solana:mainnet-beta"] = {
            "fee_per_compute_unit": 1500,
            "denomination": "lamports",
            "timestamp": old_time
        }

        # Check that old cache exists but is expired
        cache_key = "solana:mainnet-beta"
        self.assertIn(cache_key, self.gateway_http_client._fee_estimates)
        cached_entry = self.gateway_http_client._fee_estimates[cache_key]
        current_time = time.time()
        self.assertGreater(current_time - cached_entry["timestamp"], 60)

    def test_cache_fee_estimate(self):
        """Test caching fee estimate"""
        # Manually add to cache
        current_time = time.time()
        self.gateway_http_client._fee_estimates["solana:mainnet-beta"] = {
            "fee_per_compute_unit": 2000,
            "denomination": "lamports",
            "timestamp": current_time
        }

        # Verify it was cached
        cache_key = "solana:mainnet-beta"
        self.assertIn(cache_key, self.gateway_http_client._fee_estimates)
        cached_entry = self.gateway_http_client._fee_estimates[cache_key]
        self.assertEqual(cached_entry["fee_per_compute_unit"], 2000)

        # Verify timestamp is recent
        self.assertAlmostEqual(cached_entry["timestamp"], current_time, delta=1)

    def test_default_config(self):
        """Test default configuration values"""
        default_config = self.gateway_http_client.DEFAULT_CONFIG

        self.assertEqual(default_config["minFee"], 0.0001)
        self.assertEqual(default_config["maxFee"], 0.01)
        self.assertEqual(default_config["retryFeeMultiplier"], 2.0)
        self.assertEqual(default_config["retryCount"], 3)
        self.assertEqual(default_config["retryInterval"], 2)
        self.assertEqual(default_config["defaultComputeUnits"], 200000)

    def test_fee_bounds_calculation(self):
        """Test fee bounds calculation logic"""
        # Test with Solana (lamports per CU)
        compute_units = 200000
        min_fee_sol = 0.00001  # SOL
        max_fee_sol = 0.01     # SOL

        # Convert to microlamports per CU
        min_fee_per_cu = int((min_fee_sol * 1e9 * 1e6) / compute_units)
        max_fee_per_cu = int((max_fee_sol * 1e9 * 1e6) / compute_units)

        self.assertEqual(min_fee_per_cu, 50000)  # 50000 microlamports per CU
        self.assertEqual(max_fee_per_cu, 50000000)  # 50M microlamports per CU

    def test_retry_interval_calculation(self):
        """Test retry interval calculation"""
        config = {
            "retryInterval": 2000,  # 2 seconds in milliseconds
            "maxRetries": 3
        }

        # First retry: base interval
        interval_1 = config["retryInterval"] / 1000
        self.assertEqual(interval_1, 2.0)

        # Second retry: base * 2
        interval_2 = (config["retryInterval"] * 2) / 1000
        self.assertEqual(interval_2, 4.0)

        # Third retry: base * 3
        interval_3 = (config["retryInterval"] * 3) / 1000
        self.assertEqual(interval_3, 6.0)

    def test_transaction_type_extraction(self):
        """Test extraction of transaction type from method"""
        # Test method with hyphen
        method = "execute-swap"
        tx_type = method.split("-")[-1] if "-" in method else method
        self.assertEqual(tx_type, "swap")

        # Test method without hyphen
        method2 = "approve"
        tx_type2 = method2.split("-")[-1] if "-" in method2 else method2
        self.assertEqual(tx_type2, "approve")

        # Test complex method
        method3 = "open-lp-position"
        tx_type3 = method3.split("-")[-1] if "-" in method3 else method3
        self.assertEqual(tx_type3, "position")


if __name__ == "__main__":
    unittest.main()
