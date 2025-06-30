import unittest
from unittest.mock import AsyncMock, patch

from hummingbot.connector.gateway.gateway_connector_factory import GatewayConnectorFactory
from hummingbot.connector.gateway.gateway_lp import GatewayLp
from hummingbot.connector.gateway.gateway_swap import GatewaySwap


class TestGatewayConnectorFactory(unittest.IsolatedAsyncioTestCase):
    """Test the gateway connector factory with dynamic trading type support"""

    def setUp(self):
        self.mock_gateway_response = {
            "connectors": [
                {"name": "jupiter", "trading_types": ["swap"], "available_chains": ["solana"]},
                {"name": "meteora", "trading_types": ["clmm"], "available_chains": ["solana"]},
                {"name": "raydium", "trading_types": ["amm", "clmm"], "available_chains": ["solana"]},
                {"name": "uniswap", "trading_types": ["swap", "amm", "clmm"], "available_chains": ["ethereum"]},
            ]
        }

    @patch('hummingbot.connector.gateway.gateway_http_client.GatewayHttpClient.get_instance')
    async def test_get_connector_class_with_explicit_type(self, mock_get_instance):
        """Test getting connector class with explicit trading type"""
        # Setup mock
        mock_client = AsyncMock()
        mock_client.get_connectors = AsyncMock(return_value=self.mock_gateway_response)
        mock_get_instance.return_value = mock_client

        # Test swap type
        connector_class = await GatewayConnectorFactory.get_connector_class(
            "jupiter", "swap", "solana", "mainnet-beta"
        )
        self.assertEqual(connector_class, GatewaySwap)

        # Test AMM type
        connector_class = await GatewayConnectorFactory.get_connector_class(
            "raydium", "amm", "solana", "mainnet-beta"
        )
        self.assertEqual(connector_class, GatewayLp)

        # Test CLMM type
        connector_class = await GatewayConnectorFactory.get_connector_class(
            "meteora", "clmm", "solana", "mainnet-beta"
        )
        self.assertEqual(connector_class, GatewayLp)

    @patch('hummingbot.connector.gateway.gateway_http_client.GatewayHttpClient.get_instance')
    async def test_get_connector_class_without_type(self, mock_get_instance):
        """Test getting connector class without trading type (uses first available)"""
        # Setup mock
        mock_client = AsyncMock()
        mock_client.get_connectors = AsyncMock(return_value=self.mock_gateway_response)
        mock_get_instance.return_value = mock_client

        # Jupiter defaults to swap (only option)
        connector_class = await GatewayConnectorFactory.get_connector_class(
            "jupiter", None, "solana", "mainnet-beta"
        )
        self.assertEqual(connector_class, GatewaySwap)

        # Raydium defaults to amm (first in list)
        connector_class = await GatewayConnectorFactory.get_connector_class(
            "raydium", None, "solana", "mainnet-beta"
        )
        self.assertEqual(connector_class, GatewayLp)

        # Uniswap defaults to swap (first in list)
        connector_class = await GatewayConnectorFactory.get_connector_class(
            "uniswap", None, "ethereum", "mainnet"
        )
        self.assertEqual(connector_class, GatewaySwap)

    @patch('hummingbot.connector.gateway.gateway_http_client.GatewayHttpClient.get_instance')
    async def test_get_connector_class_invalid_type(self, mock_get_instance):
        """Test error handling for unsupported trading type"""
        # Setup mock
        mock_client = AsyncMock()
        mock_client.get_connectors = AsyncMock(return_value=self.mock_gateway_response)
        mock_get_instance.return_value = mock_client

        # Jupiter doesn't support AMM
        with self.assertRaises(ValueError) as context:
            await GatewayConnectorFactory.get_connector_class(
                "jupiter", "amm", "solana", "mainnet-beta"
            )
        self.assertIn("does not support trading type 'amm'", str(context.exception))

        # Raydium doesn't support swap
        with self.assertRaises(ValueError) as context:
            await GatewayConnectorFactory.get_connector_class(
                "raydium", "swap", "solana", "mainnet-beta"
            )
        self.assertIn("does not support trading type 'swap'", str(context.exception))

    @patch('hummingbot.connector.gateway.gateway_http_client.GatewayHttpClient.get_instance')
    async def test_get_connector_class_unknown_connector(self, mock_get_instance):
        """Test error handling for unknown connector"""
        # Setup mock
        mock_client = AsyncMock()
        mock_client.get_connectors = AsyncMock(return_value=self.mock_gateway_response)
        mock_get_instance.return_value = mock_client

        with self.assertRaises(ValueError) as context:
            await GatewayConnectorFactory.get_connector_class(
                "unknown", "swap", "solana", "mainnet-beta"
            )
        self.assertIn("Connector 'unknown' not found", str(context.exception))

    @patch('hummingbot.connector.gateway.gateway_http_client.GatewayHttpClient.get_instance')
    async def test_create_connector(self, mock_get_instance):
        """Test creating a connector instance"""
        # Setup mock
        mock_client = AsyncMock()
        mock_client.get_connectors = AsyncMock(return_value=self.mock_gateway_response)
        mock_get_instance.return_value = mock_client

        # Create a swap connector
        connector = await GatewayConnectorFactory.create_connector(
            connector_name="jupiter",
            trading_type="swap",
            chain="solana",
            network="mainnet-beta",
            wallet_address="test-wallet",
            trading_pairs=["SOL-USDC"],
        )

        self.assertIsInstance(connector, GatewaySwap)
        self.assertEqual(connector._connector_name, "jupiter")
        self.assertEqual(connector._chain, "solana")
        self.assertEqual(connector._network, "mainnet-beta")

    @patch('hummingbot.connector.gateway.gateway_http_client.GatewayHttpClient.get_instance')
    async def test_no_validation(self, mock_get_instance):
        """Test getting connector class without validation"""
        # No API call should be made when validate=False and trading_type is provided
        connector_class = await GatewayConnectorFactory.get_connector_class(
            "jupiter", "swap", "solana", "mainnet-beta", validate=False
        )
        self.assertEqual(connector_class, GatewaySwap)
        mock_get_instance.assert_not_called()


if __name__ == "__main__":
    unittest.main()
