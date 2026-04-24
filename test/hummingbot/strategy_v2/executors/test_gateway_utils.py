"""
Tests for Gateway executor utilities.
"""
import unittest
from unittest.mock import patch

from hummingbot.strategy_v2.executors.gateway_utils import (
    get_connectors_by_type,
    get_network_connectors,
    parse_provider,
    validate_and_normalize_connector,
    validate_network_connector,
)


class TestValidateAndNormalizeConnector(unittest.TestCase):
    """Tests for validate_and_normalize_connector function."""

    def setUp(self):
        """Set up test fixtures."""
        self.errors = []

        def capture_error(msg):
            self.errors.append(msg)

        self.capture_error = capture_error

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "jupiter/router",
        "meteora/clmm",
        "orca/clmm",
        "uniswap/router",
        "raydium/amm",
        "raydium/clmm",
    ])
    def test_already_normalized_router_exists(self):
        """Test connector with /router suffix that exists."""
        result, success = validate_and_normalize_connector(
            "jupiter/router", "router", self.capture_error
        )
        self.assertTrue(success)
        self.assertEqual(result, "jupiter/router")
        self.assertEqual(len(self.errors), 0)

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "jupiter/router",
        "meteora/clmm",
    ])
    def test_already_normalized_clmm_exists(self):
        """Test connector with /clmm suffix that exists."""
        result, success = validate_and_normalize_connector(
            "meteora/clmm", "clmm", self.capture_error
        )
        self.assertTrue(success)
        self.assertEqual(result, "meteora/clmm")
        self.assertEqual(len(self.errors), 0)

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "jupiter/router",
        "meteora/clmm",
    ])
    def test_base_name_auto_append_router(self):
        """Test base name auto-appends /router."""
        result, success = validate_and_normalize_connector(
            "jupiter", "router", self.capture_error
        )
        self.assertTrue(success)
        self.assertEqual(result, "jupiter/router")
        self.assertEqual(len(self.errors), 0)

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "jupiter/router",
        "meteora/clmm",
    ])
    def test_base_name_auto_append_clmm(self):
        """Test base name auto-appends /clmm."""
        result, success = validate_and_normalize_connector(
            "meteora", "clmm", self.capture_error
        )
        self.assertTrue(success)
        self.assertEqual(result, "meteora/clmm")
        self.assertEqual(len(self.errors), 0)

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "jupiter/router",
        "meteora/clmm",
    ])
    def test_wrong_type_suffix_fails(self):
        """Test connector with wrong type suffix fails."""
        result, success = validate_and_normalize_connector(
            "jupiter/clmm", "router", self.capture_error
        )
        self.assertFalse(success)
        self.assertIsNone(result)
        self.assertEqual(len(self.errors), 1)
        self.assertIn("requires /router connector type", self.errors[0])

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "jupiter/router",
        "meteora/clmm",
    ])
    def test_connector_not_found_with_suffix(self):
        """Test connector that doesn't exist with suffix."""
        result, success = validate_and_normalize_connector(
            "nonexistent/router", "router", self.capture_error
        )
        self.assertFalse(success)
        self.assertIsNone(result)
        self.assertEqual(len(self.errors), 1)
        self.assertIn("not found in Gateway", self.errors[0])

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "jupiter/router",
        "meteora/clmm",
        "raydium/amm",
    ])
    def test_base_name_wrong_type_available(self):
        """Test base name where required type doesn't exist but other types do."""
        result, success = validate_and_normalize_connector(
            "raydium", "router", self.capture_error
        )
        self.assertFalse(success)
        self.assertIsNone(result)
        self.assertEqual(len(self.errors), 1)
        self.assertIn("doesn't support /router", self.errors[0])
        self.assertIn("raydium/amm", self.errors[0])

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "jupiter/router",
        "meteora/clmm",
    ])
    def test_base_name_not_found(self):
        """Test base name that doesn't exist at all."""
        result, success = validate_and_normalize_connector(
            "nonexistent", "router", self.capture_error
        )
        self.assertFalse(success)
        self.assertIsNone(result)
        self.assertEqual(len(self.errors), 1)
        self.assertIn("not found in Gateway", self.errors[0])
        self.assertIn("Available router connectors", self.errors[0])


class TestGetConnectorsByType(unittest.TestCase):
    """Tests for get_connectors_by_type function."""

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "jupiter/router",
        "uniswap/router",
        "meteora/clmm",
        "orca/clmm",
        "raydium/amm",
    ])
    def test_get_router_connectors(self):
        """Test getting router connectors."""
        result = get_connectors_by_type("router")
        self.assertEqual(sorted(result), ["jupiter/router", "uniswap/router"])

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "jupiter/router",
        "uniswap/router",
        "meteora/clmm",
        "orca/clmm",
        "raydium/amm",
    ])
    def test_get_clmm_connectors(self):
        """Test getting CLMM connectors."""
        result = get_connectors_by_type("clmm")
        self.assertEqual(sorted(result), ["meteora/clmm", "orca/clmm"])

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "jupiter/router",
        "meteora/clmm",
    ])
    def test_get_nonexistent_type(self):
        """Test getting connectors of nonexistent type."""
        result = get_connectors_by_type("perp")
        self.assertEqual(result, [])


class TestParseProvider(unittest.TestCase):
    """Tests for parse_provider function."""

    def test_parse_provider_with_slash(self):
        """Test parsing provider with slash separator."""
        dex, trading_type = parse_provider("meteora/clmm")
        self.assertEqual(dex, "meteora")
        self.assertEqual(trading_type, "clmm")

    def test_parse_provider_without_slash(self):
        """Test parsing provider without slash uses default."""
        dex, trading_type = parse_provider("jupiter", default_trading_type="router")
        self.assertEqual(dex, "jupiter")
        self.assertEqual(trading_type, "router")

    def test_parse_provider_without_slash_different_default(self):
        """Test parsing provider without slash with clmm default."""
        dex, trading_type = parse_provider("orca", default_trading_type="clmm")
        self.assertEqual(dex, "orca")
        self.assertEqual(trading_type, "clmm")


class TestValidateNetworkConnector(unittest.TestCase):
    """Tests for validate_network_connector function."""

    def setUp(self):
        """Set up test fixtures."""
        self.errors = []

        def capture_error(msg):
            self.errors.append(msg)

        self.capture_error = capture_error

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [])
    def test_empty_gateway_connectors_skips_validation(self):
        """Test that empty GATEWAY_DEXS skips validation."""
        result = validate_network_connector("solana-mainnet-beta", self.capture_error)
        self.assertTrue(result)
        self.assertEqual(len(self.errors), 0)

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "solana-mainnet-beta",
        "ethereum-mainnet",
    ])
    def test_valid_network_connector(self):
        """Test valid network connector."""
        result = validate_network_connector("solana-mainnet-beta", self.capture_error)
        self.assertTrue(result)
        self.assertEqual(len(self.errors), 0)


class TestValidateAndNormalizeConnectorEmptyGateway(unittest.TestCase):
    """Tests for validate_and_normalize_connector with empty GATEWAY_DEXS."""

    def setUp(self):
        """Set up test fixtures."""
        self.errors = []

        def capture_error(msg):
            self.errors.append(msg)

        self.capture_error = capture_error

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [])
    def test_empty_gateway_with_suffix(self):
        """Test empty GATEWAY_DEXS with already normalized connector."""
        result, success = validate_and_normalize_connector(
            "jupiter/router", "router", self.capture_error
        )
        self.assertTrue(success)
        self.assertEqual(result, "jupiter/router")

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [])
    def test_empty_gateway_base_name(self):
        """Test empty GATEWAY_DEXS with base name normalizes it."""
        result, success = validate_and_normalize_connector(
            "meteora", "clmm", self.capture_error
        )
        self.assertTrue(success)
        self.assertEqual(result, "meteora/clmm")


class TestGetNetworkConnectors(unittest.TestCase):
    """Tests for get_network_connectors function."""

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "solana-mainnet-beta",
        "ethereum-mainnet",
        "jupiter/router",
        "meteora/clmm",
    ])
    def test_get_network_connectors(self):
        """Test getting network-style connectors."""
        result = get_network_connectors()
        self.assertEqual(sorted(result), ["ethereum-mainnet", "solana-mainnet-beta"])

    @patch("hummingbot.strategy_v2.executors.gateway_utils.GATEWAY_DEXS", [
        "jupiter/router",
        "meteora/clmm",
    ])
    def test_get_network_connectors_none_available(self):
        """Test getting network connectors when none exist."""
        result = get_network_connectors()
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
