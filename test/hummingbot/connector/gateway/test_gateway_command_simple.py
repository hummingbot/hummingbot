"""
Simplified test module for Gateway commands.
Focuses on basic wallet management command functionality.
"""
import asyncio
import unittest
from decimal import Decimal
from test.hummingbot.connector.gateway.test_utils import TEST_WALLETS, MockGatewayHTTPClient
from unittest.mock import patch


class TestGatewayCommandSimple(unittest.TestCase):
    """
    Simplified test class for Gateway command functionality
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.ev_loop)

    def setUp(self) -> None:
        super().setUp()

        # Use our mock gateway HTTP client
        self.gateway_http_mock = MockGatewayHTTPClient()

        # Patch GatewayHttpClient.get_instance
        self.gateway_instance_patcher = patch(
            'hummingbot.client.command.gateway_command.GatewayHttpClient.get_instance'
        )
        self.mock_get_instance = self.gateway_instance_patcher.start()
        self.mock_get_instance.return_value = self.gateway_http_mock

    def tearDown(self) -> None:
        self.gateway_instance_patcher.stop()
        super().tearDown()

    def async_run_with_timeout(self, coroutine, timeout: float = 1):
        return self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_mock_get_wallets_all_chains(self):
        """Test mock get_wallets without chain filter"""
        # Get all wallets
        result = self.async_run_with_timeout(self.gateway_http_mock.get_wallets())

        # Verify result contains wallets from multiple chains
        self.assertEqual(len(result), 2)
        chains = [wallet["chain"] for wallet in result]
        self.assertIn("solana", chains)
        self.assertIn("ethereum", chains)

    def test_mock_get_wallets_with_chain_filter(self):
        """Test mock get_wallets with chain filter"""
        # Get Solana wallets
        result = self.async_run_with_timeout(self.gateway_http_mock.get_wallets("solana"))

        # Verify result
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["chain"], "solana")
        self.assertEqual(result[0]["walletAddresses"][0], TEST_WALLETS["solana"]["address"])

    def test_mock_add_wallet(self):
        """Test mock add_wallet"""
        # Add wallet
        result = self.async_run_with_timeout(
            self.gateway_http_mock.add_wallet("solana", "test_private_key")
        )

        # Verify result
        self.assertIn("address", result)
        self.assertEqual(result["chain"], "solana")

        # Verify wallet was added
        wallets = self.async_run_with_timeout(self.gateway_http_mock.get_wallets("solana"))
        self.assertEqual(len(wallets), 2)  # Original + new

    def test_mock_remove_wallet(self):
        """Test mock remove_wallet"""
        # First add a wallet
        add_result = self.async_run_with_timeout(
            self.gateway_http_mock.add_wallet("ethereum", "temp_key")
        )
        new_address = add_result["address"]

        # Remove the wallet
        result = self.async_run_with_timeout(
            self.gateway_http_mock.remove_wallet("ethereum", new_address)
        )

        # Verify result
        self.assertTrue(result["success"])

    def test_gateway_instance_methods(self):
        """Test that gateway instance has required methods"""
        # Verify methods exist
        self.assertTrue(hasattr(self.gateway_http_mock, 'get_wallets'))
        self.assertTrue(hasattr(self.gateway_http_mock, 'add_wallet'))
        self.assertTrue(hasattr(self.gateway_http_mock, 'remove_wallet'))
        self.assertTrue(hasattr(self.gateway_http_mock, 'get_balances'))
        self.assertTrue(hasattr(self.gateway_http_mock, 'ping_gateway'))

        # Test ping_gateway
        ping_result = self.async_run_with_timeout(self.gateway_http_mock.ping_gateway())
        self.assertTrue(ping_result)

    def test_get_balances(self):
        """Test mock get_balances"""
        # Get balances
        wallet = TEST_WALLETS["solana"]["address"]
        balances = self.async_run_with_timeout(
            self.gateway_http_mock.get_balances("solana", "mainnet-beta", wallet, ["SOL", "USDC"])
        )

        # Verify balances
        self.assertEqual(balances["SOL"], Decimal("10.5"))
        self.assertEqual(balances["USDC"], Decimal("1000.0"))

    def test_wallet_command_integration(self):
        """Test basic wallet command flow"""
        # This simulates what the gateway wallet commands would do

        # List wallets
        all_wallets = self.async_run_with_timeout(self.gateway_http_mock.get_wallets())
        self.assertGreater(len(all_wallets), 0)

        # Add a wallet
        chain = "polygon"
        private_key = "test_polygon_key"
        add_result = self.async_run_with_timeout(
            self.gateway_http_mock.add_wallet(chain, private_key)
        )
        self.assertIn("address", add_result)

        # List wallets for that chain
        chain_wallets = self.async_run_with_timeout(
            self.gateway_http_mock.get_wallets(chain)
        )
        self.assertEqual(len(chain_wallets), 1)

        # Remove the wallet
        remove_result = self.async_run_with_timeout(
            self.gateway_http_mock.remove_wallet(chain, add_result["address"])
        )
        self.assertTrue(remove_result["success"])

        # Verify wallet was removed
        chain_wallets_after = self.async_run_with_timeout(
            self.gateway_http_mock.get_wallets(chain)
        )
        self.assertEqual(len(chain_wallets_after), 0)


if __name__ == "__main__":
    unittest.main()
