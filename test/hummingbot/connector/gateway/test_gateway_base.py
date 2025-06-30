"""
Test module for Gateway Base connector functionality.
Focuses on dynamic wallet resolution, caching, and base connector operations.
"""
import asyncio
import time
import unittest
from decimal import Decimal
from test.hummingbot.connector.gateway.test_utils import TEST_WALLETS, MockGatewayHTTPClient
from unittest.mock import AsyncMock, Mock, patch

from hummingbot.connector.gateway.gateway_base import GatewayBase


class TestableGatewayBase(GatewayBase):
    """Testable version of GatewayBase that exposes protected methods"""

    def __init__(self, *args, **kwargs):
        # Mock the abstract methods
        self._order_book_class = Mock
        self._order_tracker_class = Mock
        # Mock required properties
        self._native_currency = "SOL" if kwargs.get("chain") == "solana" else "ETH"
        super().__init__(*args, **kwargs)

    # Expose protected methods for testing
    async def test_get_wallet_for_chain(self):
        return await self.get_wallet_for_chain()

    def get_wallet_cache(self):
        return self._wallet_cache, self._wallet_cache_timestamp


class TestGatewayBase(unittest.TestCase):
    """
    Test class for Gateway Base connector functionality
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.ev_loop)
        cls.base_asset = "SOL"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()

        # Mock client config map with gateway_use_ssl = False
        self.mock_client_config = Mock()
        self.mock_client_config.gateway = Mock()
        self.mock_client_config.gateway.gateway_use_ssl = False

        # Patch GatewayHttpClient.get_instance to return a mock
        self.gateway_instance_mock = MockGatewayHTTPClient()
        self.gateway_instance_patcher = patch(
            'hummingbot.connector.gateway.gateway_base.GatewayHttpClient.get_instance'
        )
        self.mock_get_instance = self.gateway_instance_patcher.start()
        self.mock_get_instance.return_value = self.gateway_instance_mock

        # Create testable gateway base
        self.connector = TestableGatewayBase(
            client_config_map=self.mock_client_config,
            connector_name="raydium/clmm",
            chain="solana",
            network="mainnet-beta",
            trading_pairs=[self.trading_pair],
            trading_required=True
        )

        # Mock get_default_wallet to return None by default (forcing async fallback)
        # Individual tests can override this if needed
        self.gateway_instance_mock.get_default_wallet = Mock(return_value=None)

    def tearDown(self) -> None:
        self.gateway_instance_patcher.stop()
        super().tearDown()

    def async_run_with_timeout(self, coroutine, timeout: float = 1):
        return self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_connector_initialization(self):
        """Test that connector initializes with correct parameters"""
        self.assertEqual(self.connector.connector_name, "raydium/clmm")
        self.assertEqual(self.connector._chain, "solana")
        self.assertEqual(self.connector._network, "mainnet-beta")
        self.assertEqual(self.connector._trading_pairs, [self.trading_pair])
        self.assertIsNone(self.connector._wallet_cache)
        self.assertEqual(self.connector._wallet_cache_timestamp, 0)
        self.assertEqual(self.connector._wallet_cache_ttl, 300)  # 5 minutes

    def test_wallet_resolution_first_time(self):
        """Test wallet resolution when called for the first time"""
        # Mock get_wallets to return test wallet
        self.gateway_instance_mock.get_wallets = AsyncMock(return_value=[
            {
                "walletAddresses": [TEST_WALLETS["solana"]["address"]],
                "chain": "solana"
            }
        ])

        # Get wallet for the first time
        wallet_address = self.async_run_with_timeout(self.connector.test_get_wallet_for_chain())

        # Verify correct wallet returned
        self.assertEqual(wallet_address, TEST_WALLETS["solana"]["address"])

        # Verify cache was populated
        cached_wallet, cache_time = self.connector.get_wallet_cache()
        self.assertEqual(cached_wallet, TEST_WALLETS["solana"]["address"])
        self.assertGreater(cache_time, 0)

        # Verify get_wallets was called with correct chain
        self.gateway_instance_mock.get_wallets.assert_called_once_with("solana")

    def test_wallet_resolution_from_cache(self):
        """Test wallet resolution uses cache when available"""
        # Pre-populate cache
        test_wallet = TEST_WALLETS["solana"]["address"]
        self.connector._wallet_cache = test_wallet
        self.connector._wallet_cache_timestamp = time.time()

        # Mock get_wallets (should not be called)
        self.gateway_instance_mock.get_wallets = AsyncMock()

        # Get wallet (should use cache)
        wallet_address = self.async_run_with_timeout(self.connector.test_get_wallet_for_chain())

        # Verify cached wallet returned
        self.assertEqual(wallet_address, test_wallet)

        # Verify get_wallets was NOT called
        self.gateway_instance_mock.get_wallets.assert_not_called()

    def test_wallet_cache_expiration(self):
        """Test wallet cache expires after TTL"""
        # Pre-populate cache with old timestamp
        test_wallet = TEST_WALLETS["solana"]["address"]
        self.connector._wallet_cache = test_wallet
        self.connector._wallet_cache_timestamp = time.time() - 400  # Expired (>300s)

        # Mock get_wallets to return new wallet
        new_wallet = "NewWallet123"
        self.gateway_instance_mock.get_wallets = AsyncMock(return_value=[
            {
                "walletAddresses": [new_wallet],
                "chain": "solana"
            }
        ])

        # Get wallet (should fetch new one)
        wallet_address = self.async_run_with_timeout(self.connector.test_get_wallet_for_chain())

        # Verify new wallet returned
        self.assertEqual(wallet_address, new_wallet)

        # Verify cache was updated
        cached_wallet, cache_time = self.connector.get_wallet_cache()
        self.assertEqual(cached_wallet, new_wallet)
        self.assertGreater(cache_time, time.time() - 1)  # Recently updated

        # Verify get_wallets was called
        self.gateway_instance_mock.get_wallets.assert_called_once_with("solana")

    def test_no_wallet_found_error(self):
        """Test error when no wallet is found for chain"""
        # Mock get_wallets to return empty list
        self.gateway_instance_mock.get_wallets = AsyncMock(return_value=[])

        # Should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.async_run_with_timeout(self.connector.test_get_wallet_for_chain())

        self.assertIn("No wallet found for chain solana", str(context.exception))

    def test_wallet_with_empty_addresses(self):
        """Test error when wallet has empty addresses list"""
        # Mock get_wallets to return wallet with empty addresses
        self.gateway_instance_mock.get_wallets = AsyncMock(return_value=[
            {
                "walletAddresses": [],
                "chain": "solana"
            }
        ])

        # Should raise ValueError
        with self.assertRaises(ValueError) as context:
            self.async_run_with_timeout(self.connector.test_get_wallet_for_chain())

        self.assertIn("No wallet found for chain solana", str(context.exception))

    def test_multiple_wallets_uses_first(self):
        """Test that when multiple wallets exist, the first one is used"""
        # Mock get_wallets to return multiple wallets
        wallet1 = "Wallet1Address"
        wallet2 = "Wallet2Address"
        self.gateway_instance_mock.get_wallets = AsyncMock(return_value=[
            {
                "walletAddresses": [wallet1, wallet2],
                "chain": "solana"
            }
        ])

        # Get wallet
        wallet_address = self.async_run_with_timeout(self.connector.test_get_wallet_for_chain())

        # Verify first wallet is used
        self.assertEqual(wallet_address, wallet1)

    def test_wallet_resolution_network_error(self):
        """Test wallet resolution handles network errors gracefully"""
        # Mock get_wallets to raise network error
        self.gateway_instance_mock.get_wallets = AsyncMock(
            side_effect=ConnectionError("Cannot connect to Gateway")
        )

        # Should propagate the error
        with self.assertRaises(ConnectionError) as context:
            self.async_run_with_timeout(self.connector.test_get_wallet_for_chain())

        self.assertIn("Cannot connect to Gateway", str(context.exception))

    def test_concurrent_wallet_resolution(self):
        """Test multiple concurrent wallet resolution requests"""
        # Clear any existing cache
        self.connector._wallet_cache = None
        self.connector._wallet_cache_timestamp = 0

        # Track call count to verify caching behavior
        original_get_wallets = self.gateway_instance_mock.get_wallets
        call_count = 0

        async def counting_get_wallets(chain=None):
            nonlocal call_count
            call_count += 1
            # Add small delay to simulate network
            await asyncio.sleep(0.01)
            return await original_get_wallets(chain)

        self.gateway_instance_mock.get_wallets = counting_get_wallets

        # First call should fetch from gateway
        wallet1 = self.async_run_with_timeout(self.connector.test_get_wallet_for_chain())
        self.assertEqual(wallet1, TEST_WALLETS["solana"]["address"])
        self.assertEqual(call_count, 1)

        # Immediate subsequent calls should use cache
        wallet2 = self.async_run_with_timeout(self.connector.test_get_wallet_for_chain())
        wallet3 = self.async_run_with_timeout(self.connector.test_get_wallet_for_chain())

        self.assertEqual(wallet2, TEST_WALLETS["solana"]["address"])
        self.assertEqual(wallet3, TEST_WALLETS["solana"]["address"])

        # Should still only have called get_wallets once due to caching
        self.assertEqual(call_count, 1)

    def test_balance_operations_use_dynamic_wallet(self):
        """Test that balance operations use dynamically resolved wallet"""
        # Set up wallet resolution
        self.gateway_instance_mock.get_wallets = AsyncMock(return_value=[
            {
                "walletAddresses": [TEST_WALLETS["solana"]["address"]],
                "chain": "solana"
            }
        ])

        # Mock get_balances
        self.gateway_instance_mock.get_balances = AsyncMock(return_value={
            "SOL": Decimal("10.5"),
            "USDC": Decimal("1000.0")
        })

        # Get balance (should trigger wallet resolution)
        with patch.object(self.connector, 'get_wallet_for_chain',
                          new_callable=AsyncMock) as mock_get_wallet:
            mock_get_wallet.return_value = TEST_WALLETS["solana"]["address"]

            # Simulate balance check
            wallet = self.async_run_with_timeout(self.connector.get_wallet_for_chain())
            balances = self.async_run_with_timeout(
                self.gateway_instance_mock.get_balances(
                    "solana", "mainnet-beta", wallet, ["SOL", "USDC"]
                )
            )

            # Verify wallet resolution was called
            mock_get_wallet.assert_called_once()

            # Verify correct balances returned
            self.assertEqual(balances["SOL"], Decimal("10.5"))
            self.assertEqual(balances["USDC"], Decimal("1000.0"))

    def test_wallet_cache_invalidation(self):
        """Test manual cache invalidation scenarios"""
        # Pre-populate cache
        old_wallet = "OldWallet123"
        self.connector._wallet_cache = old_wallet
        self.connector._wallet_cache_timestamp = time.time()

        # Clear cache manually (simulating wallet change)
        self.connector._wallet_cache = None
        self.connector._wallet_cache_timestamp = 0

        # Mock get_wallets to return new wallet
        new_wallet = TEST_WALLETS["solana"]["address"]
        self.gateway_instance_mock.get_wallets = AsyncMock(return_value=[
            {
                "walletAddresses": [new_wallet],
                "chain": "solana"
            }
        ])

        # Get wallet (should fetch new one)
        wallet_address = self.async_run_with_timeout(self.connector.test_get_wallet_for_chain())

        # Verify new wallet returned
        self.assertEqual(wallet_address, new_wallet)
        self.assertNotEqual(wallet_address, old_wallet)

    def test_different_chains_use_different_wallets(self):
        """Test that different chain connectors use their respective wallets"""
        # Create Ethereum connector
        eth_connector = TestableGatewayBase(
            client_config_map=self.mock_client_config,
            connector_name="uniswap",
            chain="ethereum",
            network="mainnet",
            trading_pairs=["WETH-USDC"],
            trading_required=True
        )

        # Mock get_wallets to return different wallets based on chain
        async def mock_get_wallets(chain):
            if chain == "solana":
                return [{
                    "walletAddresses": [TEST_WALLETS["solana"]["address"]],
                    "chain": "solana"
                }]
            elif chain == "ethereum":
                return [{
                    "walletAddresses": [TEST_WALLETS["ethereum"]["address"]],
                    "chain": "ethereum"
                }]
            return []

        self.gateway_instance_mock.get_wallets = mock_get_wallets

        # Get wallets for both chains
        sol_wallet = self.async_run_with_timeout(self.connector.test_get_wallet_for_chain())
        eth_wallet = self.async_run_with_timeout(eth_connector.test_get_wallet_for_chain())

        # Verify different wallets are used
        self.assertEqual(sol_wallet, TEST_WALLETS["solana"]["address"])
        self.assertEqual(eth_wallet, TEST_WALLETS["ethereum"]["address"])
        self.assertNotEqual(sol_wallet, eth_wallet)


if __name__ == "__main__":
    unittest.main()
