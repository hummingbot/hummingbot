"""Test for unified gateway swap command"""
import asyncio
import unittest
from test.hummingbot.connector.gateway.test_utils import MockGatewayClient
from unittest.mock import AsyncMock, MagicMock

from hummingbot.client.command.gateway_swap_command import GatewaySwapCommand


class TestGatewaySwapUnified(unittest.TestCase):
    """Test unified gateway swap command"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.ev_loop)

    def setUp(self) -> None:
        super().setUp()

        # Create command instance
        self.command = GatewaySwapCommand()
        self.command.ev_loop = self.ev_loop

        # Mock logger
        self.mock_logger = MagicMock()
        self.command.logger = MagicMock(return_value=self.mock_logger)

        self.command.notify = MagicMock()
        self.command.app = MagicMock()
        self.command.placeholder_mode = False

        # Mock gateway instance
        self.mock_gateway = MockGatewayClient()
        self.command._get_gateway_instance = MagicMock(return_value=self.mock_gateway)

        # Add gateway methods that wrap gateway instance methods
        self.command._monitor_swap_transaction = AsyncMock()

        # Mock app prompt
        self.command.app.prompt = AsyncMock()
        self.command.app.to_stop_config = False
        self.command.app.hide_input = False
        self.command.app.change_prompt = MagicMock()

    def async_run_with_timeout(self, coroutine, timeout: float = 1):
        return self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_gateway_swap_no_connector(self):
        """Test gateway swap with no connector specified"""
        self.async_run_with_timeout(
            self.command._gateway_unified_swap()
        )

        # Should show error and usage
        self.command.notify.assert_any_call("\nError: connector is a required parameter.")
        self.command.notify.assert_any_call("Usage: gateway swap <connector> [base-quote] [side] [amount]")

    def test_gateway_swap_with_router_type(self):
        """Test gateway swap with router type connector"""
        # Mock user confirmation
        self.command.app.prompt.return_value = "yes"

        # Test with uniswap/router
        self.async_run_with_timeout(
            self.command._gateway_unified_swap(
                connector="uniswap/router",
                pair="ETH-USDC",
                side="SELL",
                amount="1"
            )
        )

        # Should get quote
        self.command.notify.assert_any_call("\nGetting swap quote from uniswap/router on mainnet...")

        # Should show transaction details
        self.command.notify.assert_any_call("\n=== Transaction Details ===")

        # Should ask for confirmation
        self.command.app.prompt.assert_called()
        prompt_call = self.command.app.prompt.call_args[1]["prompt"]
        self.assertIn("Do you want to execute this swap now", prompt_call)

        # Should execute swap
        self.command.notify.assert_any_call("\nExecuting swap...")

    def test_gateway_swap_with_amm_type(self):
        """Test gateway swap with AMM type connector"""
        # Mock user confirmation
        self.command.app.prompt.return_value = "yes"

        # Test with raydium/amm
        self.async_run_with_timeout(
            self.command._gateway_unified_swap(
                connector="raydium/amm",
                pair="SOL-USDC",
                side="BUY",
                amount="10"
            )
        )

        # Should search for pool
        self.command.notify.assert_any_call("\nSearching for SOL/USDC pool...")

        # Should find pool
        self.command.notify.assert_any_call("Found pool: 0xpool_SOL...")

    def test_gateway_swap_base_connector_auto_type(self):
        """Test gateway swap with base connector name (auto-detect type)"""
        # Mock user confirmation
        self.command.app.prompt.return_value = "yes"

        # Test with just "uniswap" (should auto-select router)
        self.async_run_with_timeout(
            self.command._gateway_unified_swap(
                connector="uniswap",
                pair="ETH-USDC",
                side="SELL",
                amount="1"
            )
        )

        # Should auto-detect router type
        self.command.notify.assert_any_call("\nGetting swap quote from uniswap/router on mainnet...")

    def test_gateway_swap_interactive_mode(self):
        """Test gateway swap in interactive mode"""
        # Mock user inputs
        self.command.app.prompt.side_effect = [
            "ETH",      # base token
            "USDC",     # quote token
            "0.5",      # amount
            "SELL",     # side
            "yes"       # confirmation
        ]

        # Test interactive mode
        self.async_run_with_timeout(
            self.command._gateway_unified_swap(
                connector="uniswap/router"
            )
        )

        # Should enter interactive mode
        self.assertEqual(self.command.app.prompt.call_count, 5)

        # Should get all parameters
        self.command.notify.assert_any_call("\nGetting swap quote from uniswap/router on mainnet...")
        self.command.notify.assert_any_call("  Pair: ETH-USDC")
        self.command.notify.assert_any_call("  Amount: 0.5")
        self.command.notify.assert_any_call("  Side: SELL")

    def test_gateway_swap_cancel(self):
        """Test canceling swap execution"""
        # Mock user declining execution
        self.command.app.prompt.return_value = "no"

        self.async_run_with_timeout(
            self.command._gateway_unified_swap(
                connector="uniswap/router",
                pair="ETH-USDC",
                side="SELL",
                amount="1"
            )
        )

        # Should show quote but not execute
        self.command.notify.assert_any_call("\nGetting swap quote from uniswap/router on mainnet...")
        self.command.notify.assert_any_call("Swap cancelled")

        # Should not execute
        for call in self.command.notify.call_args_list:
            self.assertNotIn("Executing swap", str(call))

    def test_gateway_swap_invalid_connector(self):
        """Test with invalid connector"""
        self.async_run_with_timeout(
            self.command._gateway_unified_swap(
                connector="invalid/router"
            )
        )

        # Should show error
        self.command.notify.assert_any_call("\nError: Connector 'invalid' not found.")

    def test_gateway_swap_invalid_side(self):
        """Test with invalid side"""
        self.async_run_with_timeout(
            self.command._gateway_unified_swap(
                connector="uniswap/router",
                pair="ETH-USDC",
                side="INVALID",
                amount="1"
            )
        )

        # Should show error
        self.command.notify.assert_any_call("Error: Invalid side 'INVALID'. Must be BUY or SELL.")

    def test_gateway_swap_invalid_amount(self):
        """Test with invalid amount"""
        self.async_run_with_timeout(
            self.command._gateway_unified_swap(
                connector="uniswap/router",
                pair="ETH-USDC",
                side="SELL",
                amount="-1"
            )
        )

        # Should show error
        self.command.notify.assert_any_call("Error: Amount must be greater than 0")

    def test_gateway_swap_monitor_transaction(self):
        """Test transaction monitoring after swap"""
        # Mock user confirmation
        self.command.app.prompt.return_value = "yes"

        # Mock transaction monitoring
        monitor_mock = AsyncMock()
        self.command._monitor_swap_transaction = monitor_mock

        self.async_run_with_timeout(
            self.command._gateway_unified_swap(
                connector="uniswap/router",
                pair="ETH-USDC",
                side="SELL",
                amount="1"
            )
        )

        # Should execute and monitor
        self.command.notify.assert_any_call("\n✓ Swap submitted successfully!")
        monitor_mock.assert_called_once()

    def test_gateway_swap_price_display(self):
        """Test proper price information display"""
        # Mock user confirmation
        self.command.app.prompt.return_value = "yes"

        self.async_run_with_timeout(
            self.command._gateway_unified_swap(
                connector="uniswap/router",
                pair="ETH-USDC",
                side="SELL",
                amount="1"
            )
        )

        # Should show transaction details with price info
        self.command.notify.assert_any_call("\n=== Transaction Details ===")
        self.command.notify.assert_any_call("\nPrice: 100 USDC/ETH")
        self.command.notify.assert_any_call("Slippage: 1.0%")

    def test_gateway_swap_with_quote_id(self):
        """Test swap execution with quote ID"""
        # Mock user confirmation
        self.command.app.prompt.return_value = "yes"

        self.async_run_with_timeout(
            self.command._gateway_unified_swap(
                connector="uniswap/router",
                pair="ETH-USDC",
                side="SELL",
                amount="1"
            )
        )

        # Should log quote ID
        self.mock_logger.info.assert_any_call("Swap quote ID: mock-quote-123")

    def test_gateway_swap_jupiter_solana(self):
        """Test swap with Jupiter on Solana"""
        # Mock user confirmation
        self.command.app.prompt.return_value = "yes"

        # Test with jupiter/router on Solana
        self.async_run_with_timeout(
            self.command._gateway_unified_swap(
                connector="jupiter/router",
                pair="SOL-USDC",
                side="SELL",
                amount="10"
            )
        )

        # Should get quote on Solana network
        self.command.notify.assert_any_call("\nGetting swap quote from jupiter/router on mainnet-beta...")

        # Should show transaction details
        self.command.notify.assert_any_call("\n=== Transaction Details ===")

        # Should show Solana-specific details
        self.command.notify.assert_any_call("\nYou will spend:")
        self.command.notify.assert_any_call("  Amount: 10 SOL (SOL)")

        # Should monitor transaction (chain-agnostic now)
        self.command._monitor_swap_transaction.assert_called()


if __name__ == "__main__":
    unittest.main()
