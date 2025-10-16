import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.client.command.gateway_pool_command import GatewayPoolCommand


class GatewayPoolCommandTest(unittest.TestCase):
    def setUp(self):
        self.app = MagicMock()
        self.app.notify = MagicMock()
        self.app.prompt = AsyncMock()
        self.app.to_stop_config = False

        # Create command instance with app's attributes
        self.command = type('TestCommand', (GatewayPoolCommand,), {
            'notify': self.app.notify,
            'app': self.app,
            'logger': MagicMock(return_value=MagicMock()),
            '_get_gateway_instance': MagicMock(),
            'ev_loop': None,
        })()

    def test_display_pool_info_with_new_fields(self):
        """Test display of pool information with new fields (baseTokenAddress, quoteTokenAddress, feePct)"""
        # Real data fetched from Raydium CLMM gateway
        pool_info = {
            'type': 'clmm',
            'network': 'mainnet-beta',
            'baseSymbol': 'SOL',
            'quoteSymbol': 'USDC',
            'baseTokenAddress': 'So11111111111111111111111111111111111111112',
            'quoteTokenAddress': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
            'feePct': 0.04,
            'address': '3ucNos4NbumPLZNWztqGHNFFgkHeRMBQAVemeeomsUxv'
        }

        self.command._display_pool_info(pool_info, "raydium/clmm", "SOL-USDC")

        # Verify all fields are displayed
        self.app.notify.assert_any_call("\n=== Pool Information ===")
        self.app.notify.assert_any_call("Connector: raydium/clmm")
        self.app.notify.assert_any_call("Trading Pair: SOL-USDC")
        self.app.notify.assert_any_call("Pool Type: clmm")
        self.app.notify.assert_any_call("Network: mainnet-beta")
        self.app.notify.assert_any_call("Base Token: SOL")
        self.app.notify.assert_any_call("Quote Token: USDC")
        self.app.notify.assert_any_call("Base Token Address: So11111111111111111111111111111111111111112")
        self.app.notify.assert_any_call("Quote Token Address: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        self.app.notify.assert_any_call("Fee: 0.04%")
        self.app.notify.assert_any_call("Pool Address: 3ucNos4NbumPLZNWztqGHNFFgkHeRMBQAVemeeomsUxv")

    def test_display_pool_info_missing_new_fields(self):
        """Test display handles missing new fields gracefully"""
        pool_info = {
            'type': 'amm',
            'network': 'mainnet',
            'baseSymbol': 'ETH',
            'quoteSymbol': 'USDC',
            'address': '0x123abc'
        }

        self.command._display_pool_info(pool_info, "uniswap/amm", "ETH-USDC")

        # Verify N/A is shown for missing fields
        self.app.notify.assert_any_call("Base Token Address: N/A")
        self.app.notify.assert_any_call("Quote Token Address: N/A")
        self.app.notify.assert_any_call("Fee: N/A%")

    @patch('hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.get_connector_chain_network')
    @patch('hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.get_pool')
    async def test_view_pool_success(self, mock_get_pool, mock_chain_network):
        """Test viewing pool information successfully"""
        mock_chain_network.return_value = ("solana", "mainnet-beta", None)
        # Real data fetched from Raydium CLMM gateway
        mock_get_pool.return_value = {
            'type': 'clmm',
            'network': 'mainnet-beta',
            'baseSymbol': 'SOL',
            'quoteSymbol': 'USDC',
            'baseTokenAddress': 'So11111111111111111111111111111111111111112',
            'quoteTokenAddress': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
            'feePct': 0.04,
            'address': '3ucNos4NbumPLZNWztqGHNFFgkHeRMBQAVemeeomsUxv'
        }

        gateway_instance = MagicMock()
        gateway_instance.get_connector_chain_network = mock_chain_network
        gateway_instance.get_pool = mock_get_pool
        self.command._get_gateway_instance = MagicMock(return_value=gateway_instance)

        await self.command._view_pool("raydium/clmm", "SOL-USDC")

        # Verify pool was fetched and displayed
        mock_get_pool.assert_called_once()
        self.app.notify.assert_any_call("\nFetching pool information for SOL-USDC on raydium/clmm...")

    @patch('hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.get_connector_chain_network')
    @patch('hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.get_pool')
    async def test_view_pool_not_found(self, mock_get_pool, mock_chain_network):
        """Test viewing pool when pool is not found"""
        mock_chain_network.return_value = ("solana", "mainnet-beta", None)
        mock_get_pool.return_value = {"error": "Pool not found"}

        gateway_instance = MagicMock()
        gateway_instance.get_connector_chain_network = mock_chain_network
        gateway_instance.get_pool = mock_get_pool
        self.command._get_gateway_instance = MagicMock(return_value=gateway_instance)

        await self.command._view_pool("raydium/clmm", "SOL-USDC")

        # Verify error message is shown
        self.app.notify.assert_any_call("\nError: Pool not found")
        self.app.notify.assert_any_call("Pool SOL-USDC not found on raydium/clmm")

    async def test_view_pool_invalid_connector_format(self):
        """Test viewing pool with invalid connector format"""
        await self.command._view_pool("invalid-connector", "SOL-USDC")

        self.app.notify.assert_any_call("Error: Invalid connector format 'invalid-connector'. Use format like 'uniswap/amm'")

    async def test_view_pool_invalid_trading_pair_format(self):
        """Test viewing pool with invalid trading pair format"""
        await self.command._view_pool("raydium/clmm", "SOLUSDC")

        self.app.notify.assert_any_call("Error: Invalid trading pair format 'SOLUSDC'. Use format like 'ETH-USDC'")

    @patch('hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.get_connector_chain_network')
    @patch('hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.pool_info')
    @patch('hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.add_pool')
    @patch('hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.post_restart')
    async def test_update_pool_direct_success(self, mock_restart, mock_add_pool, mock_pool_info, mock_chain_network):
        """Test adding pool directly with address"""
        mock_chain_network.return_value = ("solana", "mainnet-beta", None)
        # Mock pool_info response with fetched data from Gateway
        mock_pool_info.return_value = {
            'baseSymbol': 'SOL',
            'quoteSymbol': 'USDC',
            'baseTokenAddress': 'So11111111111111111111111111111111111111112',
            'quoteTokenAddress': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
            'feePct': 0.04
        }
        mock_add_pool.return_value = {"message": "Pool added successfully"}
        mock_restart.return_value = {}

        gateway_instance = MagicMock()
        gateway_instance.get_connector_chain_network = mock_chain_network
        gateway_instance.pool_info = mock_pool_info
        gateway_instance.add_pool = mock_add_pool
        gateway_instance.post_restart = mock_restart
        self.command._get_gateway_instance = MagicMock(return_value=gateway_instance)

        await self.command._update_pool_direct(
            "raydium/clmm",
            "SOL-USDC",
            "3ucNos4NbumPLZNWztqGHNFFgkHeRMBQAVemeeomsUxv"
        )

        # Verify pool_info was called to fetch pool data
        mock_pool_info.assert_called_once_with(
            connector="raydium/clmm",
            network="mainnet-beta",
            pool_address="3ucNos4NbumPLZNWztqGHNFFgkHeRMBQAVemeeomsUxv"
        )

        # Verify pool was added
        mock_add_pool.assert_called_once()
        call_args = mock_add_pool.call_args
        pool_data = call_args.kwargs['pool_data']

        # Check that pool_data includes the required fields
        self.assertEqual(pool_data['address'], "3ucNos4NbumPLZNWztqGHNFFgkHeRMBQAVemeeomsUxv")
        self.assertEqual(pool_data['type'], "clmm")
        self.assertEqual(pool_data['baseTokenAddress'], "So11111111111111111111111111111111111111112")
        self.assertEqual(pool_data['quoteTokenAddress'], "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        # Check optional fields
        self.assertEqual(pool_data['baseSymbol'], "SOL")
        self.assertEqual(pool_data['quoteSymbol'], "USDC")
        self.assertEqual(pool_data['feePct'], 0.04)

        # Verify success message
        self.app.notify.assert_any_call("✓ Pool successfully added!")
        mock_restart.assert_called_once()

    @patch('hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.get_connector_chain_network')
    @patch('hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.pool_info')
    @patch('hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.get_token')
    @patch('hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.add_pool')
    @patch('hummingbot.core.gateway.gateway_http_client.GatewayHttpClient.post_restart')
    async def test_update_pool_direct_missing_symbols(self, mock_restart, mock_add_pool, mock_get_token, mock_pool_info, mock_chain_network):
        """Test adding pool when symbols are missing from pool_info response"""
        mock_chain_network.return_value = ("solana", "mainnet-beta", None)
        # Mock pool_info response with null symbols (like Meteora returns)
        mock_pool_info.return_value = {
            'baseSymbol': None,
            'quoteSymbol': None,
            'baseTokenAddress': '27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4',
            'quoteTokenAddress': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
            'feePct': 0.05
        }
        # Mock get_token responses to return symbols with correct nested structure

        def get_token_side_effect(symbol_or_address, chain, network):
            if symbol_or_address == '27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4':
                return {
                    'token': {
                        'symbol': 'JUP',
                        'name': 'Jupiter',
                        'address': symbol_or_address,
                        'decimals': 6
                    },
                    'chain': chain,
                    'network': network
                }
            elif symbol_or_address == 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v':
                return {
                    'token': {
                        'symbol': 'USDC',
                        'name': 'USD Coin',
                        'address': symbol_or_address,
                        'decimals': 6
                    },
                    'chain': chain,
                    'network': network
                }
            return {}

        mock_get_token.side_effect = get_token_side_effect
        mock_add_pool.return_value = {"message": "Pool added successfully"}
        mock_restart.return_value = {}

        gateway_instance = MagicMock()
        gateway_instance.get_connector_chain_network = mock_chain_network
        gateway_instance.pool_info = mock_pool_info
        gateway_instance.get_token = mock_get_token
        gateway_instance.add_pool = mock_add_pool
        gateway_instance.post_restart = mock_restart
        self.command._get_gateway_instance = MagicMock(return_value=gateway_instance)

        await self.command._update_pool_direct(
            "meteora/clmm",
            "JUP-USDC",
            "5cuy7pMhTPhVZN9xuhgSbykRb986iGJb6vnEtkuBrSU"
        )

        # Verify get_token was called to fetch symbols
        self.assertEqual(mock_get_token.call_count, 2)

        # Verify pool was added with correct symbols and required fields
        mock_add_pool.assert_called_once()
        call_args = mock_add_pool.call_args
        pool_data = call_args.kwargs['pool_data']

        # Check required fields
        self.assertEqual(pool_data['address'], "5cuy7pMhTPhVZN9xuhgSbykRb986iGJb6vnEtkuBrSU")
        self.assertEqual(pool_data['type'], "clmm")
        self.assertEqual(pool_data['baseTokenAddress'], "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4")
        self.assertEqual(pool_data['quoteTokenAddress'], "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        # Check optional fields
        self.assertEqual(pool_data['baseSymbol'], "JUP")
        self.assertEqual(pool_data['quoteSymbol'], "USDC")
        self.assertEqual(pool_data['feePct'], 0.05)

    def test_display_pool_info_uniswap_clmm(self):
        """Test display of Uniswap V3 CLMM pool information with real data from EVM chain"""
        # Real data fetched from Uniswap V3 CLMM gateway on Ethereum
        pool_info = {
            'type': 'clmm',
            'network': 'mainnet',
            'baseSymbol': 'USDC',
            'quoteSymbol': 'WETH',
            'baseTokenAddress': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            'quoteTokenAddress': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
            'feePct': 0.05,
            'address': '0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640'
        }

        self.command._display_pool_info(pool_info, "uniswap/clmm", "USDC-WETH")

        # Verify all fields are displayed
        self.app.notify.assert_any_call("\n=== Pool Information ===")
        self.app.notify.assert_any_call("Connector: uniswap/clmm")
        self.app.notify.assert_any_call("Trading Pair: USDC-WETH")
        self.app.notify.assert_any_call("Pool Type: clmm")
        self.app.notify.assert_any_call("Network: mainnet")
        self.app.notify.assert_any_call("Base Token: USDC")
        self.app.notify.assert_any_call("Quote Token: WETH")
        self.app.notify.assert_any_call("Base Token Address: 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")
        self.app.notify.assert_any_call("Quote Token Address: 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
        self.app.notify.assert_any_call("Fee: 0.05%")
        self.app.notify.assert_any_call("Pool Address: 0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640")

    def test_display_pool_info_uniswap_amm(self):
        """Test display of Uniswap V2 AMM pool information with real data from EVM chain"""
        # Real data fetched from Uniswap V2 AMM gateway on Ethereum
        pool_info = {
            'type': 'amm',
            'network': 'mainnet',
            'baseSymbol': 'USDC',
            'quoteSymbol': 'WETH',
            'baseTokenAddress': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            'quoteTokenAddress': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
            'feePct': 0.3,
            'address': '0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc'
        }

        self.command._display_pool_info(pool_info, "uniswap/amm", "USDC-WETH")

        # Verify all fields are displayed
        self.app.notify.assert_any_call("\n=== Pool Information ===")
        self.app.notify.assert_any_call("Connector: uniswap/amm")
        self.app.notify.assert_any_call("Trading Pair: USDC-WETH")
        self.app.notify.assert_any_call("Pool Type: amm")
        self.app.notify.assert_any_call("Network: mainnet")
        self.app.notify.assert_any_call("Base Token: USDC")
        self.app.notify.assert_any_call("Quote Token: WETH")
        self.app.notify.assert_any_call("Base Token Address: 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")
        self.app.notify.assert_any_call("Quote Token Address: 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
        self.app.notify.assert_any_call("Fee: 0.3%")
        self.app.notify.assert_any_call("Pool Address: 0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc")


if __name__ == "__main__":
    unittest.main()
