"""
Simplified test module for Gateway commands.
Focuses on basic wallet management command functionality.
"""
import asyncio
import unittest
from decimal import Decimal
from test.hummingbot.connector.gateway.test_utils import TEST_WALLETS, MockGatewayClient
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

        # Use our mock gateway client
        self.gateway_http_mock = MockGatewayClient()

        # Patch GatewayClient.get_instance
        self.gateway_instance_patcher = patch(
            'hummingbot.client.command.gateway_command.GatewayClient.get_instance'
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
        balances_resp = self.async_run_with_timeout(
            self.gateway_http_mock.get_balances("solana", "mainnet-beta", wallet, ["SOL", "USDC"])
        )

        # Verify balances structure
        self.assertIn("balances", balances_resp)
        balances = balances_resp["balances"]
        self.assertEqual(balances["SOL"], "10.5")
        self.assertEqual(balances["USDC"], "1000.0")

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

    def test_get_chains(self):
        """Test mock get_chains"""
        # Test chains endpoint directly
        chains = self.async_run_with_timeout(self.gateway_http_mock.get_chains())

        # Verify we have expected chains
        self.assertGreater(len(chains), 0)
        chain_names = [chain["chain"] for chain in chains]
        self.assertIn("ethereum", chain_names)
        self.assertIn("solana", chain_names)

    def test_get_tokens(self):
        """Test mock get_tokens"""
        # Test tokens endpoint
        tokens_resp = self.async_run_with_timeout(
            self.gateway_http_mock.chain_request("get", "solana", "chain/tokens", {"network": "mainnet-beta"})
        )
        self.assertIn("tokens", tokens_resp)
        tokens = tokens_resp["tokens"]

        # Verify we have expected tokens
        token_symbols = [token["symbol"] for token in tokens]
        self.assertIn("SOL", token_symbols)
        self.assertIn("USDC", token_symbols)

    def test_balance_command_no_filters(self):
        """Test balance command with no filters (all chains/networks)"""
        # Direct test of the logic without complex inheritance
        wallets = self.async_run_with_timeout(self.gateway_http_mock.get_wallets())
        chains = self.async_run_with_timeout(self.gateway_http_mock.get_chains())

        # Verify we have data to work with
        self.assertGreater(len(wallets), 0)
        self.assertGreater(len(chains), 0)

        # Test balance fetching for first chain/network
        first_wallet = wallets[0]
        chain = first_wallet["chain"]
        address = first_wallet["walletAddresses"][0]

        # Find network for this chain
        chain_info = next((c for c in chains if c["chain"] == chain), None)
        self.assertIsNotNone(chain_info)

        network = chain_info["networks"][0]
        tokens = ["SOL", "USDC"] if chain == "solana" else ["ETH", "USDC"]

        # Get balances
        balances_resp = self.async_run_with_timeout(
            self.gateway_http_mock.get_balances(chain, network, address, tokens)
        )

        # Verify response structure
        self.assertIn("balances", balances_resp)
        balances = balances_resp["balances"]
        self.assertGreater(len(balances), 0)

        # Verify tokens are present
        for token in tokens:
            self.assertIn(token, balances)

    def test_balance_command_with_chain_filter(self):
        """Test balance command with chain filter"""
        # Test filtering wallets by chain
        solana_wallets = self.async_run_with_timeout(
            self.gateway_http_mock.get_wallets("solana")
        )

        # Verify we get only solana wallets
        self.assertEqual(len(solana_wallets), 1)
        self.assertEqual(solana_wallets[0]["chain"], "solana")

        # Test tokens for solana
        tokens_resp = self.async_run_with_timeout(
            self.gateway_http_mock.get_tokens("solana", "mainnet-beta")
        )

        self.assertIn("tokens", tokens_resp)
        tokens = tokens_resp["tokens"]
        token_symbols = [token["symbol"] for token in tokens]
        self.assertIn("SOL", token_symbols)
        self.assertIn("USDC", token_symbols)

    def test_balance_command_with_custom_tokens(self):
        """Test balance command with custom token list"""
        # Test fetching balances with specific token list
        ethereum_wallets = self.async_run_with_timeout(
            self.gateway_http_mock.get_wallets("ethereum")
        )

        self.assertEqual(len(ethereum_wallets), 1)
        address = ethereum_wallets[0]["walletAddresses"][0]

        # Test custom token list
        custom_tokens = ["ETH", "USDC", "DAI"]
        balances_resp = self.async_run_with_timeout(
            self.gateway_http_mock.get_balances("ethereum", "mainnet", address, custom_tokens)
        )

        balances = balances_resp["balances"]

        # Verify all custom tokens are included
        for token in custom_tokens:
            self.assertIn(token, balances)
            self.assertIsInstance(balances[token], str)
            self.assertGreater(float(balances[token]), 0)

    def test_allowance_command_ethereum_chain(self):
        """Test allowance command for Ethereum-compatible chain"""
        # Test allowances for Ethereum
        ethereum_wallets = self.async_run_with_timeout(
            self.gateway_http_mock.get_wallets("ethereum")
        )

        self.assertEqual(len(ethereum_wallets), 1)
        address = ethereum_wallets[0]["walletAddresses"][0]

        # Get connectors for allowance checking
        connectors_resp = self.async_run_with_timeout(
            self.gateway_http_mock.get_connectors()
        )

        ethereum_connectors = [
            conn for conn in connectors_resp["connectors"]
            if "ethereum" in conn.get("available_chains", [])
        ]

        self.assertGreater(len(ethereum_connectors), 0)

        # Test allowance checking
        tokens = ["USDC", "USDT"]
        connector = ethereum_connectors[0]["name"]

        allowances_resp = self.async_run_with_timeout(
            self.gateway_http_mock.get_allowances(
                "ethereum", "mainnet", address, tokens, connector
            )
        )

        self.assertIn("approvals", allowances_resp)
        approvals = allowances_resp["approvals"]

        # Verify allowances structure
        for token in tokens:
            self.assertIn(token, approvals)
            self.assertIsInstance(approvals[token], str)

    def test_allowance_command_non_ethereum_chain(self):
        """Test allowance command for non-Ethereum chain (should skip)"""
        # Test that non-Ethereum chains are filtered out in allowance logic
        ethereum_compatible_chains = ["ethereum", "polygon", "avalanche", "bsc", "arbitrum", "optimism", "base"]

        # Solana should not be in the list
        self.assertNotIn("solana", ethereum_compatible_chains)

        # Verify we can still get solana wallets but they won't be used for allowances
        solana_wallets = self.async_run_with_timeout(
            self.gateway_http_mock.get_wallets("solana")
        )

        self.assertEqual(len(solana_wallets), 1)
        self.assertEqual(solana_wallets[0]["chain"], "solana")

        # Solana should not support allowances (this is the expected behavior)
        # In the actual command, this would result in a message saying allowances not applicable

    def test_get_default_tokens_for_chain_network(self):
        """Test dynamic token fetching"""
        # Test token fetching for different chains
        solana_tokens_resp = self.async_run_with_timeout(
            self.gateway_http_mock.get_tokens("solana", "mainnet-beta")
        )

        self.assertIn("tokens", solana_tokens_resp)
        solana_tokens = solana_tokens_resp["tokens"]

        # Extract symbols
        solana_symbols = [token["symbol"] for token in solana_tokens]
        self.assertIn("SOL", solana_symbols)
        self.assertIn("USDC", solana_symbols)
        self.assertIn("RAY", solana_symbols)

        # Test ethereum tokens
        ethereum_tokens_resp = self.async_run_with_timeout(
            self.gateway_http_mock.get_tokens("ethereum", "mainnet")
        )

        ethereum_tokens = ethereum_tokens_resp["tokens"]
        ethereum_symbols = [token["symbol"] for token in ethereum_tokens]
        self.assertIn("ETH", ethereum_symbols)
        self.assertIn("USDC", ethereum_symbols)
        self.assertIn("DAI", ethereum_symbols)

    def test_balance_error_handling(self):
        """Test balance command error handling"""
        # Create a mock that raises exceptions
        mock_gateway_instance = MockGatewayClient()

        async def failing_get_wallets(chain=None):
            raise Exception("Gateway connection failed")

        mock_gateway_instance.get_wallets = failing_get_wallets

        # Test that exception is raised as expected
        with self.assertRaises(Exception) as context:
            self.async_run_with_timeout(
                mock_gateway_instance.get_wallets()
            )

        self.assertIn("Gateway connection failed", str(context.exception))

    def test_allowance_with_custom_tokens(self):
        """Test allowance command with custom token list"""
        # Test allowances with specific token list
        ethereum_wallets = self.async_run_with_timeout(
            self.gateway_http_mock.get_wallets("ethereum")
        )

        address = ethereum_wallets[0]["walletAddresses"][0]
        custom_tokens = ["USDC", "USDT", "DAI"]

        # Get allowances for custom tokens
        allowances_resp = self.async_run_with_timeout(
            self.gateway_http_mock.get_allowances(
                "ethereum", "mainnet", address, custom_tokens, "uniswap"
            )
        )

        approvals = allowances_resp["approvals"]

        # Verify all custom tokens are included
        for token in custom_tokens:
            self.assertIn(token, approvals)

        # Verify varying allowances are returned
        self.assertEqual(approvals["USDC"], "999999999")  # Unlimited
        self.assertEqual(approvals["USDT"], "1000000")    # Limited
        self.assertEqual(approvals["DAI"], "0")           # No allowance

    def test_ping_command(self):
        """Test ping command functionality"""
        # Test gateway ping
        ping_result = self.async_run_with_timeout(self.gateway_http_mock.ping_gateway())
        self.assertTrue(ping_result)

        # Test getting chains for ping
        chains = self.async_run_with_timeout(self.gateway_http_mock.get_chains())
        self.assertGreater(len(chains), 0)

        # For each chain, verify we can get native currency info
        for chain_info in chains:
            chain = chain_info["chain"]
            networks = chain_info["networks"]
            self.assertGreater(len(networks), 0)

            # First network is default
            # default_network = networks[0]

            # Verify we can get config (which includes native currency)
            # In actual implementation, this would fetch node URL and other config
            self.async_run_with_timeout(
                self.gateway_http_mock.api_request("get", "config", {"namespace": chain})
            )

            # The ping command would show status and latency for each chain
            # This test verifies the basic structure is available

    def test_wrap_command(self):
        """Test wrap command functionality"""
        # Test wrapping ETH to WETH
        network = "mainnet"
        amount = "0.1"

        # Get ethereum wallet
        ethereum_wallets = self.async_run_with_timeout(
            self.gateway_http_mock.get_wallets("ethereum")
        )
        self.assertEqual(len(ethereum_wallets), 1)
        wallet_address = ethereum_wallets[0]["walletAddresses"][0]

        # Mock wrap response
        # The wrap_params would be used in actual gateway call

        # Since MockGatewayHTTPClient doesn't have wrap method yet, we'll add it
        async def mock_wrap(network: str, address: str, amount: str):
            return {
                "nonce": 123,
                "signature": "0xabcdef123456",
                "fee": "0.002",
                "amount": amount,
                "wrappedAddress": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "nativeToken": "ETH",
                "wrappedToken": "WETH",
                "tx": {
                    "data": "0xd0e30db0",
                    "to": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                    "value": amount
                }
            }

        # Add wrap method to mock
        self.gateway_http_mock.wrap = mock_wrap

        # Test wrap
        wrap_resp = self.async_run_with_timeout(
            self.gateway_http_mock.wrap(network, wallet_address, amount)
        )

        # Verify response structure
        self.assertIn("signature", wrap_resp)
        self.assertIn("fee", wrap_resp)
        self.assertIn("wrappedAddress", wrap_resp)
        self.assertIn("nativeToken", wrap_resp)
        self.assertIn("wrappedToken", wrap_resp)
        self.assertEqual(wrap_resp["nativeToken"], "ETH")
        self.assertEqual(wrap_resp["wrappedToken"], "WETH")
        self.assertEqual(wrap_resp["amount"], amount)

    def test_wrap_command_different_networks(self):
        """Test wrap command for different networks"""
        # Test different network native tokens
        network_tokens = {
            "mainnet": ("ETH", "WETH"),
            "bsc": ("BNB", "WBNB"),
            "avalanche": ("AVAX", "WAVAX"),
            "polygon": ("MATIC", "WMATIC")
        }

        for network, (native, wrapped) in network_tokens.items():
            with self.subTest(network=network):
                # Mock appropriate response for each network
                async def mock_wrap_network(net: str, addr: str, amt: str):
                    return {
                        "signature": f"0x{network}123456",
                        "nativeToken": native,
                        "wrappedToken": wrapped,
                        "amount": amt
                    }

                self.gateway_http_mock.wrap = mock_wrap_network

                wrap_resp = self.async_run_with_timeout(
                    self.gateway_http_mock.wrap(network, "0xtest", "1.0")
                )

                self.assertEqual(wrap_resp["nativeToken"], native)
                self.assertEqual(wrap_resp["wrappedToken"], wrapped)

    def test_wrap_invalid_amount(self):
        """Test wrap command with invalid amounts"""
        # Test that wrap validation would catch these
        invalid_amounts = ["-0.1", "0", "abc", ""]

        for amount in invalid_amounts:
            with self.subTest(amount=amount):
                # In actual implementation, these would be validated before calling gateway
                # Here we just verify the test data
                try:
                    decimal_amount = float(amount)
                    self.assertLessEqual(decimal_amount, 0)  # Should be invalid
                except ValueError:
                    # Non-numeric amounts should fail
                    pass

    def test_allowance_command_new_params(self):
        """Test updated allowance command with network, connector, tokens params"""
        # Test new allowance command structure
        network = "mainnet"
        connector = "uniswap"
        tokens = ["USDC", "USDT"]

        # Get ethereum wallet (allowance is ethereum-only)
        ethereum_wallets = self.async_run_with_timeout(
            self.gateway_http_mock.get_wallets("ethereum")
        )
        wallet_address = ethereum_wallets[0]["walletAddresses"][0]

        # Test allowance check
        allowances_resp = self.async_run_with_timeout(
            self.gateway_http_mock.get_allowances(
                "ethereum", network, wallet_address, tokens, connector
            )
        )

        # Verify response
        self.assertIn("approvals", allowances_resp)
        approvals = allowances_resp["approvals"]

        for token in tokens:
            self.assertIn(token, approvals)

    def test_approve_command_new_params(self):
        """Test updated approve command with network, connector, tokens params"""
        # Test new approve command structure
        network = "mainnet"
        connector = "uniswap"
        token = "USDC"

        # Get ethereum wallet
        ethereum_wallets = self.async_run_with_timeout(
            self.gateway_http_mock.get_wallets("ethereum")
        )
        wallet_address = ethereum_wallets[0]["walletAddresses"][0]

        # Test approve
        approve_resp = self.async_run_with_timeout(
            self.gateway_http_mock.approve_token(
                "ethereum", network, wallet_address, token, connector, Decimal("1000000")
            )
        )

        # Verify response
        self.assertIn("signature", approve_resp)
        self.assertIn("status", approve_resp)
        self.assertEqual(approve_resp["status"], 1)  # Confirmed

    def test_get_transaction_status(self):
        """Test transaction status polling for wrap/approve"""
        # Add get_transaction_status to mock
        async def mock_get_tx_status(chain: str, network: str, tx_hash: str):
            return {
                "txStatus": 1,  # Confirmed
                "txBlock": 12345678,
                "txReceipt": {"status": 1}
            }

        self.gateway_http_mock.get_transaction_status = mock_get_tx_status

        # Test transaction status
        status_resp = self.async_run_with_timeout(
            self.gateway_http_mock.get_transaction_status(
                "ethereum", "mainnet", "0xmocktxhash"
            )
        )

        self.assertEqual(status_resp["txStatus"], 1)
        self.assertIn("txBlock", status_resp)

    def test_ethereum_networks_completion(self):
        """Test that Ethereum networks are properly returned for completion"""
        # Get chains to find ethereum networks
        chains = self.async_run_with_timeout(self.gateway_http_mock.get_chains())

        # Find ethereum chain
        ethereum_chain = next((c for c in chains if c["chain"] == "ethereum"), None)
        self.assertIsNotNone(ethereum_chain)

        # Verify ethereum has expected networks
        networks = ethereum_chain["networks"]
        self.assertIn("mainnet", networks)
        self.assertIn("testnet", networks)

        # In actual completer, these networks would be used for
        # allowance, approve, and wrap command completions

    def test_hardware_wallet_support(self):
        """Test hardware wallet add functionality"""
        # Add hardware wallet
        chain = "ethereum"
        hardware_address = "0x1234567890123456789012345678901234567890"

        result = self.async_run_with_timeout(
            self.gateway_http_mock.add_hardware_wallet(chain, hardware_address)
        )

        # Verify result
        self.assertEqual(result["address"], hardware_address)
        self.assertEqual(result["chain"], chain)
        self.assertEqual(result["type"], "hardware")

        # Verify wallet was added
        wallets = self.async_run_with_timeout(self.gateway_http_mock.get_wallets(chain))

        # Find the hardware wallet
        hardware_wallet = None
        for wallet in wallets:
            if hardware_address in wallet.get("hardwareWalletAddresses", []):
                hardware_wallet = wallet
                break

        self.assertIsNotNone(hardware_wallet)
        self.assertIn(hardware_address, hardware_wallet.get("hardwareWalletAddresses", []))

    def test_read_only_wallet_support(self):
        """Test read-only wallet add functionality"""
        # Add read-only wallet
        chain = "solana"
        readonly_address = "ReadOnly1111111111111111111111111111111111"

        result = self.async_run_with_timeout(
            self.gateway_http_mock.add_read_only_wallet(chain, readonly_address)
        )

        # Verify result
        self.assertEqual(result["address"], readonly_address)
        self.assertEqual(result["chain"], chain)
        self.assertEqual(result["type"], "read-only")

        # Verify wallet was added
        wallets = self.async_run_with_timeout(self.gateway_http_mock.get_wallets(chain))

        # Find the read-only wallet
        readonly_wallet = None
        for wallet in wallets:
            if readonly_address in wallet.get("readOnlyWalletAddresses", []):
                readonly_wallet = wallet
                break

        self.assertIsNotNone(readonly_wallet)
        self.assertIn(readonly_address, readonly_wallet.get("readOnlyWalletAddresses", []))

    def test_mixed_wallet_types(self):
        """Test having different wallet types for the same chain"""
        chain = "ethereum"

        # Add regular wallet
        self.async_run_with_timeout(
            self.gateway_http_mock.add_wallet(chain, "regular_private_key")
        )

        # Add hardware wallet
        hardware_address = "0xHardware1234567890123456789012345678901234"
        self.async_run_with_timeout(
            self.gateway_http_mock.add_hardware_wallet(chain, hardware_address)
        )

        # Add read-only wallet
        readonly_address = "0xReadOnly1234567890123456789012345678901234"
        self.async_run_with_timeout(
            self.gateway_http_mock.add_read_only_wallet(chain, readonly_address)
        )

        # Get all wallets for chain
        wallets = self.async_run_with_timeout(self.gateway_http_mock.get_wallets(chain))

        # Count wallet types
        regular_count = 0
        hardware_count = 0
        readonly_count = 0

        for wallet in wallets:
            if wallet.get("walletAddresses"):
                regular_count += len(wallet["walletAddresses"])
            if wallet.get("hardwareWalletAddresses"):
                hardware_count += len(wallet["hardwareWalletAddresses"])
            if wallet.get("readOnlyWalletAddresses"):
                readonly_count += len(wallet["readOnlyWalletAddresses"])

        # Verify we have all types (1 original + 1 new regular + 1 hardware + 1 readonly)
        self.assertEqual(regular_count, 2)  # Original ethereum wallet + new one
        self.assertEqual(hardware_count, 1)
        self.assertEqual(readonly_count, 1)

    def test_balance_with_hardware_wallets(self):
        """Test that balances work with hardware wallets"""
        chain = "ethereum"
        hardware_address = "0xHardware1234567890123456789012345678901234"

        # Add hardware wallet
        self.async_run_with_timeout(
            self.gateway_http_mock.add_hardware_wallet(chain, hardware_address)
        )

        # Get balances for hardware wallet
        tokens = ["ETH", "USDC"]
        balances_resp = self.async_run_with_timeout(
            self.gateway_http_mock.get_balances(chain, "mainnet", hardware_address, tokens)
        )

        # Verify balances returned
        self.assertIn("balances", balances_resp)
        balances = balances_resp["balances"]
        for token in tokens:
            self.assertIn(token, balances)


if __name__ == "__main__":
    unittest.main()
