"""
Simplified integration tests for Gateway connector functionality.
Tests basic end-to-end scenarios without complex mocking.
"""
import asyncio
import unittest
from decimal import Decimal
from test.hummingbot.connector.gateway.test_utils import TEST_WALLETS, MockGatewayConnector, MockGatewayHTTPClient
from unittest.mock import Mock, patch


class TestGatewayIntegrationSimple(unittest.TestCase):
    """
    Simplified integration test class for Gateway connector functionality
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.ev_loop)

    def setUp(self) -> None:
        super().setUp()

        # Mock gateway instance
        self.gateway_instance_mock = MockGatewayHTTPClient()

        # Mock client config
        self.mock_client_config = Mock()
        self.mock_client_config.gateway = Mock()
        self.mock_client_config.gateway.gateway_use_ssl = False

        # Patch GatewayHttpClient.get_instance
        self.gateway_instance_patcher = patch(
            'hummingbot.connector.gateway.gateway_base.GatewayHttpClient.get_instance'
        )
        self.mock_get_instance = self.gateway_instance_patcher.start()
        self.mock_get_instance.return_value = self.gateway_instance_mock

    def tearDown(self) -> None:
        self.gateway_instance_patcher.stop()
        super().tearDown()

    def async_run_with_timeout(self, coroutine, timeout: float = 1):
        return self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_complete_wallet_workflow(self):
        """Test complete wallet management workflow"""
        # Step 1: Check initial wallets
        initial_wallets = self.async_run_with_timeout(
            self.gateway_instance_mock.get_wallets()
        )
        initial_count = len(initial_wallets)
        self.assertGreater(initial_count, 0)

        # Step 2: Add a new wallet
        new_chain = "polygon"
        result = self.async_run_with_timeout(
            self.gateway_instance_mock.add_wallet(new_chain, "test_private_key_123")
        )
        self.assertIn("address", result)
        new_address = result["address"]

        # Step 3: Verify wallet was added
        all_wallets = self.async_run_with_timeout(
            self.gateway_instance_mock.get_wallets()
        )
        self.assertEqual(len(all_wallets), initial_count + 1)

        # Step 4: Get wallets for specific chain
        chain_wallets = self.async_run_with_timeout(
            self.gateway_instance_mock.get_wallets(new_chain)
        )
        self.assertEqual(len(chain_wallets), 1)
        self.assertIn(new_address, chain_wallets[0]["walletAddresses"])

        # Step 5: Check balance for new wallet
        balances = self.async_run_with_timeout(
            self.gateway_instance_mock.get_balances(
                new_chain, "mainnet", new_address, ["MATIC", "USDC"]
            )
        )
        self.assertEqual(balances["MATIC"], Decimal("10.5"))  # Native token
        self.assertEqual(balances["USDC"], Decimal("1000.0"))  # Other token

        # Step 6: Remove the wallet
        remove_result = self.async_run_with_timeout(
            self.gateway_instance_mock.remove_wallet(new_chain, new_address)
        )
        self.assertTrue(remove_result["success"])

        # Step 7: Verify wallet was removed
        final_wallets = self.async_run_with_timeout(
            self.gateway_instance_mock.get_wallets()
        )
        self.assertEqual(len(final_wallets), initial_count)

    def test_multi_chain_wallet_management(self):
        """Test managing wallets across multiple chains"""
        chains_to_test = ["solana", "ethereum", "polygon"]

        # Get initial wallet counts for each chain
        initial_counts = {}
        for chain in chains_to_test:
            wallets = self.async_run_with_timeout(
                self.gateway_instance_mock.get_wallets(chain)
            )
            initial_counts[chain] = len(wallets)

        # Verify different chains have independent wallets
        sol_wallets = self.async_run_with_timeout(
            self.gateway_instance_mock.get_wallets("solana")
        )
        eth_wallets = self.async_run_with_timeout(
            self.gateway_instance_mock.get_wallets("ethereum")
        )

        # Check addresses are different
        if sol_wallets and eth_wallets:
            sol_address = sol_wallets[0]["walletAddresses"][0]
            eth_address = eth_wallets[0]["walletAddresses"][0]
            self.assertNotEqual(sol_address, eth_address)

            # Solana addresses don't start with 0x
            self.assertFalse(sol_address.startswith("0x"))
            # Ethereum addresses do start with 0x
            self.assertTrue(eth_address.startswith("0x"))

    def test_connector_wallet_resolution(self):
        """Test that connectors can resolve wallets dynamically"""
        # Create a mock connector
        connector = MockGatewayConnector(
            connector_name="raydium/clmm",
            chain="solana",
            network="mainnet-beta"
        )
        connector._gateway_instance = self.gateway_instance_mock

        # Get wallet for the connector's chain
        wallet_address = self.async_run_with_timeout(
            connector.get_wallet_for_chain()
        )

        # Verify it matches the expected wallet
        self.assertEqual(wallet_address, TEST_WALLETS["solana"]["address"])

        # Verify caching works
        wallet_address2 = self.async_run_with_timeout(
            connector.get_wallet_for_chain()
        )
        self.assertEqual(wallet_address, wallet_address2)

    def test_balance_and_allowance_operations(self):
        """Test balance and allowance operations"""
        # Test Ethereum balance and allowance
        eth_wallet = TEST_WALLETS["ethereum"]["address"]

        # Get balances
        balances = self.async_run_with_timeout(
            self.gateway_instance_mock.get_balances(
                "ethereum", "mainnet", eth_wallet, ["ETH", "USDC", "DAI"]
            )
        )

        # Verify balances
        self.assertEqual(balances["ETH"], Decimal("10.5"))  # Native token
        self.assertEqual(balances["USDC"], Decimal("1000.0"))
        self.assertEqual(balances["DAI"], Decimal("1000.0"))

        # Get allowances
        spender = "0x1111111111111111111111111111111111111111"
        allowances = self.async_run_with_timeout(
            self.gateway_instance_mock.get_allowances(
                "ethereum", "mainnet", eth_wallet, ["USDC", "DAI"], spender
            )
        )

        # Verify allowances
        self.assertEqual(allowances["USDC"], Decimal("999999999"))
        self.assertEqual(allowances["DAI"], Decimal("999999999"))

        # Test approve
        approve_result = self.async_run_with_timeout(
            self.gateway_instance_mock.approve_token(
                "ethereum", "mainnet", eth_wallet, "USDC", spender, Decimal("1000000")
            )
        )

        # Verify approval
        self.assertEqual(approve_result["signature"], "mockApproveTx123")
        self.assertEqual(approve_result["status"], 1)
        self.assertTrue(approve_result["confirmed"])

    def test_wallet_not_found_handling(self):
        """Test handling when no wallet is found for a chain"""
        # Remove all wallets for a test chain
        test_chain = "avalanche"

        # Verify no wallets exist
        wallets = self.async_run_with_timeout(
            self.gateway_instance_mock.get_wallets(test_chain)
        )
        self.assertEqual(len(wallets), 0)

        # Create a mock connector for this chain
        connector = MockGatewayConnector(
            connector_name="trader_joe",
            chain=test_chain,
            network="mainnet"
        )
        connector._gateway_instance = self.gateway_instance_mock

        # Try to get wallet - should raise error
        with self.assertRaises(ValueError) as context:
            self.async_run_with_timeout(connector.get_wallet_for_chain())

        self.assertIn(f"No wallet found for chain {test_chain}", str(context.exception))

        # Add a wallet
        add_result = self.async_run_with_timeout(
            self.gateway_instance_mock.add_wallet(test_chain, "test_key")
        )

        # Clear cache to force re-fetch
        connector._wallet_cache = None
        connector._wallet_cache_timestamp = 0

        # Now it should work
        wallet_address = self.async_run_with_timeout(
            connector.get_wallet_for_chain()
        )
        self.assertEqual(wallet_address, add_result["address"])

    def test_concurrent_connector_operations(self):
        """Test multiple connectors operating concurrently"""
        # Create multiple connectors on same chain
        connector1 = MockGatewayConnector(
            connector_name="raydium/clmm",
            chain="solana",
            network="mainnet-beta"
        )
        connector1._gateway_instance = self.gateway_instance_mock

        connector2 = MockGatewayConnector(
            connector_name="orca",
            chain="solana",
            network="mainnet-beta"
        )
        connector2._gateway_instance = self.gateway_instance_mock

        # Get wallets concurrently
        async def get_wallets_concurrent():
            wallet1, wallet2 = await asyncio.gather(
                connector1.get_wallet_for_chain(),
                connector2.get_wallet_for_chain()
            )
            return wallet1, wallet2

        wallet1, wallet2 = self.async_run_with_timeout(get_wallets_concurrent())

        # Both should use the same wallet
        self.assertEqual(wallet1, wallet2)
        self.assertEqual(wallet1, TEST_WALLETS["solana"]["address"])


if __name__ == "__main__":
    unittest.main()
