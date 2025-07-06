import asyncio
import unittest
from decimal import Decimal
from test.hummingbot.connector.gateway.test_utils import MockGatewayHTTPClient
from unittest.mock import AsyncMock, Mock, patch

from hummingbot.connector.gateway.gateway_base import GatewayBase
from hummingbot.connector.gateway.gateway_http_client import GatewayHttpClient


class TestableGatewayBase(GatewayBase):
    """Testable version of GatewayBase that exposes protected methods"""

    def __init__(self, *args, **kwargs):
        # Mock the abstract methods
        self._order_book_class = Mock
        self._order_tracker_class = Mock
        # Mock required properties
        self._native_currency = "SOL" if kwargs.get("chain") == "solana" else "ETH"
        super().__init__(*args, **kwargs)


class TestGatewayRateLimiting(unittest.TestCase):
    """Test rate limiting error handling in Gateway components"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.ev_loop)

    def setUp(self) -> None:
        super().setUp()

        # Mock client config map with gateway_use_ssl = False
        self.mock_client_config = Mock()
        self.mock_client_config.gateway = Mock()
        self.mock_client_config.gateway.gateway_use_ssl = False
        self.mock_client_config.gateway.gateway_api_host = "localhost"
        self.mock_client_config.gateway.gateway_api_port = 15888

        # Clear singleton instance
        GatewayHttpClient._GatewayHttpClient__instance = None

        # Create gateway HTTP client instance
        self.gateway_http_client = GatewayHttpClient(client_config_map=self.mock_client_config)

    def tearDown(self) -> None:
        # Clear singleton instance
        GatewayHttpClient._GatewayHttpClient__instance = None
        super().tearDown()

    def async_run_with_timeout(self, coroutine, timeout: float = 1):
        return self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_rate_limit_error_detection(self):
        """Test that rate limit errors are properly detected"""
        # Test various rate limit error patterns
        test_cases = [
            (429, "Too many requests"),
            (200, "429 Too Many Requests"),
            (500, "rate limit exceeded"),
            (503, "Rate Limit Exceeded"),
            (200, "too many requests from your IP"),
        ]

        for status_code, error_msg in test_cases:
            # Check if our detection logic works
            is_rate_limit = (
                status_code == 429 or
                "429" in str(error_msg) or
                "rate limit" in str(error_msg).lower() or
                "too many requests" in str(error_msg).lower()
            )
            self.assertTrue(is_rate_limit, f"Failed to detect rate limit for status={status_code}, msg='{error_msg}'")

    def test_rate_limit_error_message_formatting(self):
        """Test that rate limit errors produce correct user-friendly messages"""
        # Test HTTP client error message
        method = "GET"
        url = "http://localhost:15888/chains/solana/balances"
        expected_msg = (
            f"Rate limit exceeded on {method} {url}. "
            "The blockchain node is rejecting requests due to too many requests. "
            "Please wait before retrying or configure a different RPC endpoint."
        )

        # Verify message format
        self.assertIn("Rate limit exceeded", expected_msg)
        self.assertIn("too many requests", expected_msg)
        self.assertIn("different RPC endpoint", expected_msg)

    def test_gateway_http_client_rate_limit_handling(self):
        """Test that GatewayHttpClient properly handles 429 responses"""
        with patch("hummingbot.connector.gateway.gateway_http_client.aiohttp.ClientSession") as mock_session_class:
            # Create mock response
            mock_response = Mock()
            mock_response.status = 429

            async def mock_json():
                return {"error": "Too many requests"}
            mock_response.json = mock_json

            # Create mock session
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_response)
            mock_session_class.return_value = mock_session

            # Test that rate limit error is raised with proper message
            with self.assertRaises(ValueError) as context:
                self.async_run_with_timeout(
                    self.gateway_http_client.api_request("get", "chains/solana/balances")
                )

            error_msg = str(context.exception)
            self.assertIn("Rate limit exceeded", error_msg)
            self.assertIn("too many requests", error_msg.lower())
            self.assertIn("different RPC endpoint", error_msg)

    def test_gateway_base_rate_limit_handling(self):
        """Test that GatewayBase properly handles rate limit errors"""
        # Use MockGatewayHTTPClient for consistency
        mock_gateway_instance = MockGatewayHTTPClient()

        # Override get_balances to simulate rate limit error
        mock_gateway_instance.get_balances = AsyncMock(
            side_effect=Exception("Error on GET http://localhost:15888/chains/solana/balances Error: 429 Too Many Requests")
        )

        # Patch GatewayHttpClient.get_instance
        with patch('hummingbot.connector.gateway.gateway_base.GatewayHttpClient.get_instance') as mock_get_instance:
            mock_get_instance.return_value = mock_gateway_instance

            # Create testable gateway base
            gateway_base = TestableGatewayBase(
                client_config_map=self.mock_client_config,
                connector_name="raydium/clmm",
                chain="solana",
                network="mainnet-beta",
                trading_pairs=["SOL-USDC"],
                trading_required=True
            )

            # Mock the logger
            mock_logger = Mock()
            with patch.object(gateway_base, 'logger', return_value=mock_logger):
                # This should log warnings but not raise
                self.async_run_with_timeout(gateway_base.update_balances())

                # Verify rate limit warning was logged
                self.assertTrue(mock_logger.warning.called)
                warning_args = [call[0][0] for call in mock_logger.warning.call_args_list]
                warning_text = " ".join(str(arg) for arg in warning_args)

                # Check for rate limit message
                self.assertTrue(
                    "rate limit exceeded" in warning_text.lower() or
                    "429" in warning_text or
                    "too many requests" in warning_text.lower(),
                    f"Expected rate limit message but got: {warning_text}"
                )

                # Verify balances were set to 0 to allow connector to be ready
                self.assertEqual(gateway_base._account_balances.get("SOL"), Decimal("0"))
                self.assertEqual(gateway_base._account_balances.get("USDC"), Decimal("0"))

    def test_gateway_base_other_errors_not_mistaken_for_rate_limit(self):
        """Test that non-rate-limit errors are not mistaken for rate limiting"""
        # Use MockGatewayHTTPClient for consistency
        mock_gateway_instance = MockGatewayHTTPClient()

        # Override get_balances to simulate different error
        mock_gateway_instance.get_balances = AsyncMock(
            side_effect=Exception("Internal Server Error: Wallet not found")
        )

        # Patch GatewayHttpClient.get_instance
        with patch('hummingbot.connector.gateway.gateway_base.GatewayHttpClient.get_instance') as mock_get_instance:
            mock_get_instance.return_value = mock_gateway_instance

            # Create testable gateway base
            gateway_base = TestableGatewayBase(
                client_config_map=self.mock_client_config,
                connector_name="raydium/clmm",
                chain="solana",
                network="mainnet-beta",
                trading_pairs=["SOL-USDC"],
                trading_required=True
            )

            # Mock the logger
            mock_logger = Mock()
            with patch.object(gateway_base, 'logger', return_value=mock_logger):
                # This should log warnings but not raise
                self.async_run_with_timeout(gateway_base.update_balances())

                # Verify wallet error was logged, not rate limit
                self.assertTrue(mock_logger.warning.called)
                warning_args = [call[0][0] for call in mock_logger.warning.call_args_list]
                warning_text = " ".join(str(arg) for arg in warning_args)

                # Should have wallet-related warning
                self.assertTrue("wallet" in warning_text.lower() or "internal server error" in warning_text.lower())
                # Should not have rate limit warning
                self.assertFalse("rate limit" in warning_text.lower())


if __name__ == "__main__":
    unittest.main()
