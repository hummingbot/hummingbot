"""Test for GatewayHttpClient class."""
import unittest
from unittest.mock import AsyncMock, Mock, patch

from hummingbot.connector.gateway.core.gateway_http_client import GatewayHttpClient


class TestGatewayHttpClient(unittest.IsolatedAsyncioTestCase):
    """Test Gateway HTTP client functionality."""

    def setUp(self):
        # Mock client config
        self.mock_client_config = Mock()
        self.mock_client_config.gateway = Mock()
        self.mock_client_config.gateway.gateway_api_host = "localhost"
        self.mock_client_config.gateway.gateway_api_port = 15888
        self.mock_client_config.gateway.gateway_use_ssl = False
        self.mock_client_config.certs_path = "/path/to/certs"

        # Reset singleton
        GatewayHttpClient._GatewayHttpClient__instance = None

    async def test_get_instance_singleton(self):
        """Test that GatewayHttpClient is a singleton."""
        client1 = GatewayHttpClient.get_instance(self.mock_client_config)
        client2 = GatewayHttpClient.get_instance(self.mock_client_config)
        self.assertIs(client1, client2)

    async def test_base_url_construction(self):
        """Test base URL construction with HTTP and HTTPS."""
        # Test HTTP
        client = GatewayHttpClient.get_instance(self.mock_client_config)
        self.assertEqual(client.base_url, "http://localhost:15888")

        # Test HTTPS
        GatewayHttpClient._GatewayHttpClient__instance = None
        self.mock_client_config.gateway.gateway_use_ssl = True
        client = GatewayHttpClient.get_instance(self.mock_client_config)
        self.assertEqual(client.base_url, "https://localhost:15888")

    @patch('aiohttp.ClientSession')
    async def test_request_methods(self, mock_session_class):
        """Test various HTTP request methods."""
        # Setup mock session
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "success"})

        # Configure mocks for different methods
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.put = AsyncMock(return_value=mock_response)
        mock_session.delete = AsyncMock(return_value=mock_response)
        mock_session.closed = False

        mock_session_class.return_value = mock_session

        client = GatewayHttpClient.get_instance(self.mock_client_config)
        client._shared_session = mock_session

        # Test GET request
        result = await client.request("GET", "test")
        self.assertEqual(result, {"result": "success"})
        mock_session.get.assert_called_once()

        # Test POST request
        result = await client.request("POST", "test", data={"key": "value"})
        self.assertEqual(result, {"result": "success"})
        mock_session.post.assert_called_once()

        # Test PUT request
        result = await client.request("PUT", "test", data={"key": "value"})
        self.assertEqual(result, {"result": "success"})
        mock_session.put.assert_called_once()

        # Test DELETE request
        result = await client.request("DELETE", "test", data={"key": "value"})
        self.assertEqual(result, {"result": "success"})
        mock_session.delete.assert_called_once()

    @patch('aiohttp.ClientSession')
    async def test_wallet_methods(self, mock_session_class):
        """Test wallet management methods."""
        # Setup mock
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock()
        mock_session.closed = False

        mock_session_class.return_value = mock_session
        client = GatewayHttpClient.get_instance(self.mock_client_config)
        client._shared_session = mock_session

        # Test get_wallets
        mock_response.json.return_value = [{"chain": "ethereum", "walletAddresses": ["0x123"]}]
        mock_session.get = AsyncMock(return_value=mock_response)
        result = await client.get_wallets()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["chain"], "ethereum")

        # Test add_wallet
        mock_response.json.return_value = {"address": "0x456"}
        mock_session.post = AsyncMock(return_value=mock_response)
        result = await client.add_wallet("ethereum", "private_key_here")
        self.assertEqual(result["address"], "0x456")

        # Test remove_wallet
        mock_response.json.return_value = {"success": True}
        mock_session.delete = AsyncMock(return_value=mock_response)
        result = await client.remove_wallet("ethereum", "0x123")
        self.assertTrue(result["success"])

        # Test add_hardware_wallet
        mock_response.json.return_value = {"address": "0x789", "type": "hardware"}
        mock_session.post = AsyncMock(return_value=mock_response)
        result = await client.add_hardware_wallet("ethereum", "0x789")
        self.assertEqual(result["address"], "0x789")

    @patch('aiohttp.ClientSession')
    async def test_chain_and_connector_methods(self, mock_session_class):
        """Test chain and connector information methods."""
        # Setup mock
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_session.closed = False

        mock_session_class.return_value = mock_session
        client = GatewayHttpClient.get_instance(self.mock_client_config)
        client._shared_session = mock_session

        # Test get_chains
        mock_response.json.return_value = {"chains": [{"chain": "ethereum", "networks": ["mainnet"]}]}
        mock_session.get = AsyncMock(return_value=mock_response)
        result = await client.get_chains()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["chain"], "ethereum")

        # Test get_connectors
        mock_response.json.return_value = {
            "connectors": [
                {"name": "uniswap", "trading_types": ["amm", "clmm"]}
            ]
        }
        mock_session.get = AsyncMock(return_value=mock_response)
        result = await client.get_connectors()
        self.assertIn("uniswap", result)
        self.assertEqual(result["uniswap"]["trading_types"], ["amm", "clmm"])

    @patch('aiohttp.ClientSession')
    async def test_connector_request(self, mock_session_class):
        """Test connector request method."""
        # Setup mock
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"price": "100.5"})
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.closed = False

        mock_session_class.return_value = mock_session
        client = GatewayHttpClient.get_instance(self.mock_client_config)
        client._shared_session = mock_session

        # Test connector request
        result = await client.connector_request(
            "GET", "uniswap/amm", "quote-swap",
            params={"baseToken": "ETH", "quoteToken": "USDC"}
        )
        self.assertEqual(result["price"], "100.5")
        mock_session.get.assert_called_once()
        args = mock_session.get.call_args
        self.assertIn("connectors/uniswap/amm/quote-swap", args[0][0])

    @patch('aiohttp.ClientSession')
    async def test_error_handling(self, mock_session_class):
        """Test error handling in requests."""
        # Setup mock
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad request")
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.closed = False

        mock_session_class.return_value = mock_session
        client = GatewayHttpClient.get_instance(self.mock_client_config)
        client._shared_session = mock_session

        # Test error response
        with self.assertRaises(Exception) as context:
            await client.request("GET", "test")
        self.assertIn("Gateway request failed", str(context.exception))

    async def test_cache_management(self):
        """Test internal cache management."""
        client = GatewayHttpClient.get_instance(self.mock_client_config)

        # Test internal cache attributes exist
        self.assertIsInstance(client._config_cache, dict)
        self.assertIsInstance(client._connector_info_cache, dict)
        self.assertIsInstance(client._chain_info_cache, list)
        self.assertIsInstance(client._wallets_cache, dict)

        # Test cache TTL
        self.assertEqual(client._cache_ttl, 300)  # 5 minutes

    @patch('aiohttp.ClientSession')
    async def test_gateway_initialization(self, mock_session_class):
        """Test gateway initialization method."""
        # Setup mock
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_session.closed = False

        # Mock responses for initialization
        chains_response = {"chains": [{"chain": "ethereum", "networks": ["mainnet"]}]}
        connectors_response = {"connectors": [{"name": "uniswap", "trading_types": ["amm"]}]}
        wallets_response = [{"chain": "ethereum", "walletAddresses": ["0x123"]}]
        namespaces_response = {"namespaces": ["ethereum-mainnet"]}

        mock_response.json = AsyncMock()
        mock_response.json.side_effect = [
            chains_response,
            connectors_response,
            wallets_response,
            namespaces_response
        ]

        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session_class.return_value = mock_session

        client = GatewayHttpClient.get_instance(self.mock_client_config)
        client._shared_session = mock_session

        # Run initialization
        await client.initialize_gateway()

        # Verify caches were populated
        self.assertEqual(len(client._chain_info_cache), 1)
        self.assertIn("uniswap", client._connector_info_cache)
        self.assertIn("ethereum", client._wallets_cache)
        self.assertTrue(client._cache_initialized)

    @patch('aiohttp.ClientSession')
    async def test_get_default_network_for_chain(self, mock_session_class):
        """Test get_default_network_for_chain method."""
        # Setup mock
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"defaultNetwork": "mainnet"})
        mock_session.closed = False
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session_class.return_value = mock_session

        client = GatewayHttpClient.get_instance(self.mock_client_config)
        client._shared_session = mock_session

        # Test successful retrieval
        network = await client.get_default_network_for_chain("ethereum")
        self.assertEqual(network, "mainnet")

    @patch('aiohttp.ClientSession')
    async def test_get_default_wallet_for_chain(self, mock_session_class):
        """Test get_default_wallet_for_chain method."""
        # Setup mock
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"defaultWallet": "0x123456"})
        mock_session.closed = False
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session_class.return_value = mock_session

        client = GatewayHttpClient.get_instance(self.mock_client_config)
        client._shared_session = mock_session

        # Test successful retrieval
        wallet = await client.get_default_wallet_for_chain("ethereum")
        self.assertEqual(wallet, "0x123456")

    @patch('aiohttp.ClientSession')
    async def test_get_native_currency_symbol(self, mock_session_class):
        """Test get_native_currency_symbol method."""
        # Setup mock
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"nativeCurrencySymbol": "ETH"})
        mock_session.closed = False
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session_class.return_value = mock_session

        client = GatewayHttpClient.get_instance(self.mock_client_config)
        client._shared_session = mock_session

        # Test successful retrieval
        symbol = await client.get_native_currency_symbol("ethereum", "mainnet")
        self.assertEqual(symbol, "ETH")


if __name__ == "__main__":
    unittest.main()
