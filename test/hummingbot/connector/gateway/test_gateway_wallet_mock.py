"""
Test module for Gateway wallet management using mock implementation.
Tests wallet functionality without requiring actual Gateway connection.
"""
import asyncio
import unittest
from decimal import Decimal
from test.hummingbot.connector.gateway.test_utils import TEST_WALLETS, MockGatewayHttpClient


class TestGatewayWalletMock(unittest.TestCase):
    """
    Test class for Gateway wallet management functionality using mocks
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.ev_loop)

    def setUp(self) -> None:
        super().setUp()

        # Create mock gateway client
        self.client = MockGatewayHttpClient()

    def async_run_with_timeout(self, coroutine, timeout: float = 1):
        return self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_get_wallets_all_chains(self):
        """Test getting all wallets without chain filter"""
        # Call get_wallets without chain filter
        result = self.async_run_with_timeout(self.client.get_wallets())

        # Verify result contains wallets from multiple chains
        self.assertEqual(len(result), 2)
        chains = [wallet["chain"] for wallet in result]
        self.assertIn("solana", chains)
        self.assertIn("ethereum", chains)

        # Verify wallet addresses
        sol_wallet = next(w for w in result if w["chain"] == "solana")
        self.assertEqual(sol_wallet["walletAddresses"][0], TEST_WALLETS["solana"]["address"])

    def test_get_wallets_with_chain_filter(self):
        """Test getting wallets for a specific chain"""
        # Call get_wallets with chain filter
        result = self.async_run_with_timeout(self.client.get_wallets("solana"))

        # Verify result
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["chain"], "solana")
        self.assertEqual(result[0]["walletAddresses"][0], TEST_WALLETS["solana"]["address"])

    def test_get_wallets_empty_chain(self):
        """Test getting wallets for a chain with no wallets"""
        # Call get_wallets for non-existent chain
        result = self.async_run_with_timeout(self.client.get_wallets("polygon"))

        # Verify empty result
        self.assertEqual(result, [])

    def test_add_wallet_success(self):
        """Test successful wallet addition"""
        # Add wallet
        result = self.async_run_with_timeout(
            self.client.add_wallet("solana", "test_private_key_123")
        )

        # Verify result
        self.assertIn("address", result)
        self.assertEqual(result["chain"], "solana")
        self.assertIn("New", result["address"])  # Mock generates addresses starting with "New"

        # Verify wallet was added
        wallets = self.async_run_with_timeout(self.client.get_wallets("solana"))
        self.assertEqual(len(wallets), 2)  # Original + new wallet

    def test_add_wallet_different_chains(self):
        """Test adding wallets to different chains"""
        # Add Ethereum wallet
        eth_result = self.async_run_with_timeout(
            self.client.add_wallet("ethereum", "eth_private_key")
        )
        self.assertIn("0xNew", eth_result["address"])  # Ethereum addresses start with 0x

        # Add Polygon wallet (new chain)
        poly_result = self.async_run_with_timeout(
            self.client.add_wallet("polygon", "poly_private_key")
        )
        self.assertIn("0xNew", poly_result["address"])

        # Verify wallets were added to correct chains
        eth_wallets = self.async_run_with_timeout(self.client.get_wallets("ethereum"))
        poly_wallets = self.async_run_with_timeout(self.client.get_wallets("polygon"))

        self.assertEqual(len(eth_wallets), 2)  # Original + new
        self.assertEqual(len(poly_wallets), 1)  # Only new

    def test_remove_wallet_success(self):
        """Test successful wallet removal"""
        # First add a wallet
        add_result = self.async_run_with_timeout(
            self.client.add_wallet("solana", "temp_key")
        )
        new_address = add_result["address"]

        # Verify it was added
        wallets_before = self.async_run_with_timeout(self.client.get_wallets("solana"))
        self.assertEqual(len(wallets_before), 2)

        # Remove the wallet
        remove_result = self.async_run_with_timeout(
            self.client.remove_wallet("solana", new_address)
        )

        # Verify result
        self.assertTrue(remove_result["success"])

        # Verify wallet was removed
        wallets_after = self.async_run_with_timeout(self.client.get_wallets("solana"))
        self.assertEqual(len(wallets_after), 1)
        self.assertEqual(wallets_after[0]["walletAddresses"][0], TEST_WALLETS["solana"]["address"])

    def test_remove_non_existent_wallet(self):
        """Test removing a wallet that doesn't exist"""
        # Try to remove non-existent wallet
        result = self.async_run_with_timeout(
            self.client.remove_wallet("solana", "non_existent_address")
        )

        # Mock still returns success (simplified behavior)
        self.assertTrue(result["success"])

        # Verify original wallets unchanged
        wallets = self.async_run_with_timeout(self.client.get_wallets("solana"))
        self.assertEqual(len(wallets), 1)

    def test_multiple_wallet_operations(self):
        """Test multiple wallet operations in sequence"""
        # Add multiple wallets
        addresses = []
        for i in range(3):
            result = self.async_run_with_timeout(
                self.client.add_wallet("solana", f"key_{i}")
            )
            addresses.append(result["address"])

        # Verify all were added
        wallets = self.async_run_with_timeout(self.client.get_wallets("solana"))
        self.assertEqual(len(wallets), 4)  # 1 original + 3 new

        # Remove middle wallet
        self.async_run_with_timeout(
            self.client.remove_wallet("solana", addresses[1])
        )

        # Verify count
        wallets = self.async_run_with_timeout(self.client.get_wallets("solana"))
        self.assertEqual(len(wallets), 3)

    def test_wallet_operations_async(self):
        """Test concurrent wallet operations"""
        async def concurrent_adds():
            # Add wallets concurrently
            results = await asyncio.gather(
                self.client.add_wallet("solana", "concurrent_1"),
                self.client.add_wallet("ethereum", "concurrent_2"),
                self.client.add_wallet("polygon", "concurrent_3")
            )
            return results

        results = self.async_run_with_timeout(concurrent_adds())

        # Verify all operations completed
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["chain"], "solana")
        self.assertEqual(results[1]["chain"], "ethereum")
        self.assertEqual(results[2]["chain"], "polygon")

    def test_balance_operations(self):
        """Test balance-related operations"""
        # Get balance for a wallet
        wallet = TEST_WALLETS["solana"]["address"]
        balances = self.async_run_with_timeout(
            self.client.get_balances("solana", "mainnet-beta", wallet, ["SOL", "USDC"])
        )

        # Verify mock balances - gateway returns wrapped response
        self.assertIn("balances", balances)
        balance_dict = balances["balances"]
        self.assertEqual(Decimal(balance_dict["SOL"]), Decimal("10.5"))
        self.assertEqual(Decimal(balance_dict["USDC"]), Decimal("1000.0"))

    def test_allowance_operations(self):
        """Test allowance-related operations"""
        # Get allowances
        wallet = TEST_WALLETS["ethereum"]["address"]
        allowances = self.async_run_with_timeout(
            self.client.get_allowances(
                "ethereum", "mainnet", wallet, ["USDC", "DAI"], "0xspender"
            )
        )

        # Verify mock allowances - gateway returns wrapped response
        self.assertIn("approvals", allowances)
        approval_dict = allowances["approvals"]
        self.assertEqual(Decimal(approval_dict["USDC"]), Decimal("999999999"))
        self.assertEqual(Decimal(approval_dict["DAI"]), Decimal("0"))  # DAI has no allowance per mock

    def test_approve_token(self):
        """Test token approval"""
        # Approve token
        wallet = TEST_WALLETS["ethereum"]["address"]
        result = self.async_run_with_timeout(
            self.client.approve_token(
                "ethereum", "mainnet", wallet, "USDC", "0xspender", Decimal("1000")
            )
        )

        # Verify mock response
        self.assertEqual(result["signature"], "mockApproveTx123")
        self.assertEqual(result["status"], 1)
        self.assertTrue(result["confirmed"])


if __name__ == "__main__":
    unittest.main()
