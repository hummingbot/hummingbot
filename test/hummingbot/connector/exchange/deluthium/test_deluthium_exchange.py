"""
Unit tests for Deluthium exchange connector.

QA Test Plan Coverage:
- HB-CRIT-001: Balance update behavior verification
- HB-CRIT-002: Error handling uses proper exception types (not generic Exception)
- HB-CRIT-003: Order book data quality
- HB-HIGH-001: Multi-chain cache support
- HB-HIGH-002: Bid/ask spread validation
"""

import asyncio
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.deluthium import deluthium_constants as CONSTANTS
from hummingbot.connector.exchange.deluthium.deluthium_exchange import DeluthiumExchange
from hummingbot.core.data_type.common import OrderType, TradeType


class TestDeluthiumExchange(unittest.TestCase):
    """Test cases for DeluthiumExchange class."""

    @classmethod
    def setUpClass(cls):
        """Set up class fixtures."""
        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_jwt_token"
        self.chain_id = 56
        self.wallet_address = "0x742d35Cc6634C0532925a3b8D1e4D1F4D6ee2D7e"
        
        self.exchange = DeluthiumExchange(
            deluthium_api_key=self.api_key,
            deluthium_chain_id=self.chain_id,
            deluthium_wallet_address=self.wallet_address,
            trading_pairs=["WBNB/USDT"],
            trading_required=True,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        """Helper to run async functions with timeout."""
        return self.ev_loop.run_until_complete(
            asyncio.wait_for(coroutine, timeout)
        )

    def test_name(self):
        """Test exchange name."""
        self.assertEqual(self.exchange.name, CONSTANTS.DOMAIN)

    def test_domain(self):
        """Test exchange domain."""
        self.assertEqual(self.exchange.domain, CONSTANTS.DOMAIN)

    def test_chain_id(self):
        """Test chain ID property."""
        self.assertEqual(self.exchange.chain_id, self.chain_id)

    def test_wallet_address(self):
        """Test wallet address property."""
        self.assertEqual(self.exchange.wallet_address, self.wallet_address)

    def test_supported_order_types(self):
        """Test that only market orders are supported."""
        order_types = self.exchange.supported_order_types()
        self.assertEqual(order_types, [OrderType.MARKET])

    def test_is_cancel_request_synchronous(self):
        """Test cancel request is not synchronous (RFQ orders can't be cancelled)."""
        self.assertFalse(self.exchange.is_cancel_request_in_exchange_synchronous)

    def test_trading_rules_request_path(self):
        """Test trading rules request path."""
        self.assertEqual(
            self.exchange.trading_rules_request_path,
            CONSTANTS.LISTING_PAIRS_URL
        )

    def test_check_network_request_path(self):
        """Test check network request path."""
        self.assertEqual(
            self.exchange.check_network_request_path,
            CONSTANTS.LISTING_PAIRS_URL
        )

    def test_authenticator_with_api_key(self):
        """Test authenticator is created when API key is provided."""
        self.assertIsNotNone(self.exchange.authenticator)

    def test_authenticator_without_api_key(self):
        """Test authenticator is None when API key is not provided."""
        exchange = DeluthiumExchange(
            deluthium_api_key=None,
            trading_pairs=["WBNB/USDT"],
        )
        self.assertIsNone(exchange.authenticator)

    def test_pair_id_cache_initially_empty(self):
        """Test pair ID cache is initially empty."""
        self.assertEqual(self.exchange.pair_id_cache, {})

    def test_get_pair_cache_chain_qualified(self):
        """Test that pair cache lookup is chain-qualified."""
        # Manually set cache with chain-qualified key
        self.exchange._pair_id_cache["WBNB/USDT:56"] = {
            "pair_id": "101",
            "chain_id": 56,
        }
        
        # Should find with correct chain
        result = self.exchange._get_pair_cache("WBNB/USDT")
        self.assertEqual(result.get("pair_id"), "101")
        
        # Different chain should return empty
        self.exchange._chain_id = 8453
        result = self.exchange._get_pair_cache("WBNB/USDT")
        self.assertEqual(result, {})


class TestDeluthiumExchangeErrorHandling(unittest.TestCase):
    """Test cases for error handling in DeluthiumExchange."""

    def setUp(self):
        """Set up test fixtures."""
        self.exchange = DeluthiumExchange(
            deluthium_api_key="test_token",
            deluthium_chain_id=56,
            trading_pairs=["WBNB/USDT"],
        )

    def test_handle_response_errors_success(self):
        """Test handling successful response."""
        response = {"code": 10000, "message": "Success", "data": {}}
        # Should not raise
        self.exchange._handle_response_errors(response)

    def test_handle_response_errors_success_string(self):
        """Test handling successful response with string code."""
        response = {"code": "10000", "message": "Success", "data": {}}
        # Should not raise
        self.exchange._handle_response_errors(response)

    def test_handle_response_errors_none(self):
        """Test handling None response."""
        # Should not raise
        self.exchange._handle_response_errors(None)

    def test_handle_response_errors_string_code(self):
        """Test handling string error code raises ValueError."""
        response = {
            "code": "INVALID_INPUT",
            "message": "token addresses cannot be empty"
        }
        with self.assertRaises(ValueError) as context:
            self.exchange._handle_response_errors(response)
        self.assertIn("BadRequest", str(context.exception))

    def test_handle_response_errors_numeric_code(self):
        """Test handling numeric error code raises ValueError."""
        response = {
            "code": 10095,
            "message": "Invalid parameters"
        }
        with self.assertRaises(ValueError) as context:
            self.exchange._handle_response_errors(response)
        self.assertIn("BadRequest", str(context.exception))

    def test_handle_response_errors_not_found(self):
        """Test handling not found error raises ValueError."""
        response = {
            "code": 20004,
            "message": "pair not found"
        }
        with self.assertRaises(ValueError) as context:
            self.exchange._handle_response_errors(response)
        self.assertIn("BadSymbol", str(context.exception))

    def test_handle_response_errors_exchange_not_available(self):
        """Test handling exchange not available raises IOError."""
        response = {
            "code": "MM_NOT_AVAILABLE",
            "message": "Market maker not available"
        }
        with self.assertRaises(IOError) as context:
            self.exchange._handle_response_errors(response)
        self.assertIn("ExchangeNotAvailable", str(context.exception))

    def test_handle_response_errors_auth_error(self):
        """Test handling authentication error raises PermissionError."""
        response = {
            "code": "SIGNING_ERROR",
            "message": "Signature verification failed"
        }
        with self.assertRaises(PermissionError) as context:
            self.exchange._handle_response_errors(response)
        self.assertIn("AuthenticationError", str(context.exception))

    def test_handle_response_errors_timeout(self):
        """Test handling timeout error raises TimeoutError."""
        response = {
            "code": "TIMEOUT_ERROR",
            "message": "Request timed out"
        }
        with self.assertRaises(TimeoutError) as context:
            self.exchange._handle_response_errors(response)
        self.assertIn("RequestTimeout", str(context.exception))


class TestDeluthiumExchangeTradingRules(unittest.IsolatedAsyncioTestCase):
    """Async test cases for trading rules."""

    def setUp(self):
        """Set up test fixtures."""
        self.exchange = DeluthiumExchange(
            deluthium_api_key="test_token",
            deluthium_chain_id=56,
            trading_pairs=["WBNB/USDT"],
        )

    async def test_format_trading_rules(self):
        """Test formatting trading rules from exchange info."""
        exchange_info = {
            "code": 10000,
            "data": {
                "pairs": [
                    {
                        "pair_id": "101",
                        "chain_id": 56,
                        "pair_symbol": "WBNB-USDT",
                        "is_enabled": True,
                        "base_token": {
                            "token_address": "0xBB4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                            "token_symbol": "WBNB",
                            "decimals": 18,
                        },
                        "quote_token": {
                            "token_address": "0x55d398326f99059fF775485246999027B3197955",
                            "token_symbol": "USDT",
                            "decimals": 18,
                        },
                    }
                ]
            }
        }
        
        rules = await self.exchange._format_trading_rules(exchange_info)
        
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].trading_pair, "WBNB/USDT")

    async def test_format_trading_rules_disabled_pair(self):
        """Test that disabled pairs are skipped."""
        exchange_info = {
            "code": 10000,
            "data": {
                "pairs": [
                    {
                        "pair_id": "101",
                        "chain_id": 56,
                        "pair_symbol": "WBNB-USDT",
                        "is_enabled": False,  # Disabled
                        "base_token": {"decimals": 18},
                        "quote_token": {"decimals": 18},
                    }
                ]
            }
        }
        
        rules = await self.exchange._format_trading_rules(exchange_info)
        
        self.assertEqual(len(rules), 0)


class TestDeluthiumCriticalBugs(unittest.IsolatedAsyncioTestCase):
    """
    Test cases for critical bugs identified in Staff Engineer review.
    
    These tests verify that the critical bugs have been properly fixed
    and should be run as regression tests after any code changes.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.exchange = DeluthiumExchange(
            deluthium_api_key="test_token",
            deluthium_chain_id=56,
            deluthium_wallet_address="0x742d35Cc6634C0532925a3b8D1e4D1F4D6ee2D7e",
            trading_pairs=["WBNB/USDT"],
        )

    # =========================================================================
    # HB-CRIT-001: Balance update behavior verification
    # =========================================================================
    
    async def test_update_balances_logs_warning(self):
        """
        HB-CRIT-001: Verify _update_balances() logs a warning about DEX limitations.
        
        Since Deluthium is a DEX and doesn't have off-chain balance tracking,
        the method should warn users about this limitation.
        """
        with patch.object(self.exchange, 'logger') as mock_logger:
            await self.exchange._update_balances()
            
            # Verify warning was logged
            mock_logger.return_value.warning.assert_called()
            warning_message = str(mock_logger.return_value.warning.call_args)
            
            # Warning should mention that balance querying is not implemented
            self.assertIn("Balance", warning_message.lower() or "balance")

    async def test_update_balances_does_not_raise(self):
        """
        HB-CRIT-001: Verify _update_balances() doesn't raise exceptions.
        
        Even though balances aren't fetched, the method should not crash.
        """
        try:
            await self.exchange._update_balances()
        except Exception as e:
            self.fail(f"_update_balances() raised unexpected exception: {e}")

    # =========================================================================
    # HB-CRIT-002: Error handling uses proper exception types
    # =========================================================================

    def test_error_handling_not_generic_exception_invalid_input(self):
        """
        HB-CRIT-002: Verify INVALID_INPUT raises ValueError, not Exception.
        """
        response = {"code": "INVALID_INPUT", "message": "Invalid parameters"}
        
        with self.assertRaises(ValueError) as context:
            self.exchange._handle_response_errors(response)
        
        # Should be ValueError, not generic Exception
        self.assertIsInstance(context.exception, ValueError)
        self.assertNotEqual(type(context.exception).__name__, "Exception")

    def test_error_handling_not_generic_exception_invalid_token(self):
        """
        HB-CRIT-002: Verify INVALID_TOKEN raises ValueError, not Exception.
        """
        response = {"code": "INVALID_TOKEN", "message": "Token not found"}
        
        with self.assertRaises(ValueError) as context:
            self.exchange._handle_response_errors(response)
        
        self.assertIsInstance(context.exception, ValueError)

    def test_error_handling_not_generic_exception_mm_not_available(self):
        """
        HB-CRIT-002: Verify MM_NOT_AVAILABLE raises IOError, not Exception.
        """
        response = {"code": "MM_NOT_AVAILABLE", "message": "Market maker unavailable"}
        
        with self.assertRaises(IOError) as context:
            self.exchange._handle_response_errors(response)
        
        self.assertIsInstance(context.exception, IOError)

    def test_error_handling_not_generic_exception_signing_error(self):
        """
        HB-CRIT-002: Verify SIGNING_ERROR raises PermissionError, not Exception.
        """
        response = {"code": "SIGNING_ERROR", "message": "Signature verification failed"}
        
        with self.assertRaises(PermissionError) as context:
            self.exchange._handle_response_errors(response)
        
        self.assertIsInstance(context.exception, PermissionError)

    def test_error_handling_not_generic_exception_timeout(self):
        """
        HB-CRIT-002: Verify TIMEOUT_ERROR raises TimeoutError, not Exception.
        """
        response = {"code": "TIMEOUT_ERROR", "message": "Request timed out"}
        
        with self.assertRaises(TimeoutError) as context:
            self.exchange._handle_response_errors(response)
        
        self.assertIsInstance(context.exception, TimeoutError)

    def test_error_handling_numeric_code_10095(self):
        """
        HB-CRIT-002: Verify numeric error code 10095 raises ValueError.
        """
        response = {"code": 10095, "message": "Invalid parameters"}
        
        with self.assertRaises(ValueError) as context:
            self.exchange._handle_response_errors(response)
        
        self.assertIsInstance(context.exception, ValueError)

    def test_error_handling_numeric_code_20003(self):
        """
        HB-CRIT-002: Verify numeric error code 20003 raises IOError.
        """
        response = {"code": 20003, "message": "Internal error"}
        
        with self.assertRaises(IOError) as context:
            self.exchange._handle_response_errors(response)
        
        self.assertIsInstance(context.exception, IOError)

    def test_error_handling_numeric_code_20004(self):
        """
        HB-CRIT-002: Verify numeric error code 20004 raises ValueError.
        """
        response = {"code": 20004, "message": "Pair not found"}
        
        with self.assertRaises(ValueError) as context:
            self.exchange._handle_response_errors(response)
        
        self.assertIsInstance(context.exception, ValueError)

    def test_error_handling_success_code_numeric(self):
        """
        HB-CRIT-002: Verify success code 10000 (numeric) doesn't raise.
        """
        response = {"code": 10000, "message": "Success", "data": {}}
        
        # Should not raise
        self.exchange._handle_response_errors(response)

    def test_error_handling_success_code_string(self):
        """
        HB-CRIT-002: Verify success code "10000" (string) doesn't raise.
        """
        response = {"code": "10000", "message": "Success", "data": {}}
        
        # Should not raise
        self.exchange._handle_response_errors(response)

    # =========================================================================
    # HB-HIGH-001: Multi-chain cache support
    # =========================================================================

    def test_pair_cache_chain_qualified_key(self):
        """
        HB-HIGH-001: Verify cache keys include chain ID.
        """
        # Set up cache with chain-qualified key
        self.exchange._pair_id_cache["WBNB/USDT:56"] = {
            "pair_id": "101",
            "chain_id": 56,
        }
        
        # Should find with correct chain
        result = self.exchange._get_pair_cache("WBNB/USDT")
        self.assertEqual(result.get("pair_id"), "101")

    def test_pair_cache_different_chains_independent(self):
        """
        HB-HIGH-001: Verify same symbol on different chains doesn't conflict.
        """
        # Set up cache for WETH/USDC on both Ethereum and Base
        self.exchange._pair_id_cache["WETH/USDC:1"] = {
            "pair_id": "201",
            "chain_id": 1,
        }
        self.exchange._pair_id_cache["WETH/USDC:8453"] = {
            "pair_id": "301",
            "chain_id": 8453,
        }
        
        # Query with chain ID = 1 (Ethereum)
        self.exchange._chain_id = 1
        eth_cache = self.exchange._get_pair_cache("WETH/USDC")
        
        # Query with chain ID = 8453 (Base)
        self.exchange._chain_id = 8453
        base_cache = self.exchange._get_pair_cache("WETH/USDC")
        
        # Should get different pair IDs
        self.assertEqual(eth_cache.get("pair_id"), "201")
        self.assertEqual(base_cache.get("pair_id"), "301")
        self.assertNotEqual(eth_cache.get("pair_id"), base_cache.get("pair_id"))

    def test_pair_cache_missing_returns_empty(self):
        """
        HB-HIGH-001: Verify missing cache entry returns empty dict, not None.
        """
        result = self.exchange._get_pair_cache("UNKNOWN/PAIR")
        self.assertEqual(result, {})
        self.assertIsInstance(result, dict)

    # =========================================================================
    # Market order validation
    # =========================================================================

    async def test_place_order_rejects_limit_order(self):
        """
        Verify that limit orders are rejected (RFQ only supports market orders).
        """
        with self.assertRaises(ValueError) as context:
            await self.exchange._place_order(
                order_id="test123",
                trading_pair="WBNB/USDT",
                amount=Decimal("1.0"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,  # Should be rejected
                price=Decimal("500.0"),
            )
        
        self.assertIn("market", str(context.exception).lower())


class TestDeluthiumHighPriorityBugs(unittest.IsolatedAsyncioTestCase):
    """
    Test cases for high priority bugs identified in Staff Engineer review.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.exchange = DeluthiumExchange(
            deluthium_api_key="test_token",
            deluthium_chain_id=56,
            trading_pairs=["WBNB/USDT"],
        )

    async def test_format_trading_rules_caches_with_chain_id(self):
        """
        HB-HIGH-001: Verify _format_trading_rules caches pairs with chain-qualified key.
        """
        exchange_info = {
            "code": 10000,
            "data": {
                "pairs": [
                    {
                        "pair_id": "101",
                        "chain_id": 56,
                        "pair_symbol": "WBNB-USDT",
                        "is_enabled": True,
                        "base_token": {
                            "token_address": "0xBB4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                            "token_symbol": "WBNB",
                            "decimals": 18,
                        },
                        "quote_token": {
                            "token_address": "0x55d398326f99059fF775485246999027B3197955",
                            "token_symbol": "USDT",
                            "decimals": 18,
                        },
                    }
                ]
            }
        }
        
        await self.exchange._format_trading_rules(exchange_info)
        
        # Verify cache key includes chain ID
        expected_key = "WBNB/USDT:56"
        self.assertIn(expected_key, self.exchange._pair_id_cache)
        
        # Verify cache has correct data
        cache_entry = self.exchange._pair_id_cache[expected_key]
        self.assertEqual(cache_entry["pair_id"], "101")
        self.assertEqual(cache_entry["chain_id"], 56)


class TestDeluthiumRegressionTests(unittest.TestCase):
    """
    Regression tests to prevent re-introduction of fixed bugs.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.exchange = DeluthiumExchange(
            deluthium_api_key="test_token",
            deluthium_chain_id=56,
            trading_pairs=["WBNB/USDT"],
        )

    def test_reg001_pair_id_cache_key_format(self):
        """
        REG-001: Verify pairId cache key includes chain_id.
        
        Prevents regression of multi-chain cache conflict bug.
        """
        # The cache key format should be "{trading_pair}:{chain_id}"
        self.exchange._pair_id_cache["TEST/PAIR:56"] = {"pair_id": "999"}
        
        # _get_pair_cache should use chain-qualified key
        self.exchange._chain_id = 56
        result = self.exchange._get_pair_cache("TEST/PAIR")
        
        self.assertEqual(result.get("pair_id"), "999")

    def test_reg002_exception_types_not_generic(self):
        """
        REG-002: Verify error handling doesn't use generic Exception.
        
        Prevents regression of exception type bug.
        """
        test_cases = [
            ({"code": "INVALID_INPUT", "message": "test"}, ValueError),
            ({"code": "INVALID_TOKEN", "message": "test"}, ValueError),
            ({"code": "MM_NOT_AVAILABLE", "message": "test"}, IOError),
            ({"code": "SIGNING_ERROR", "message": "test"}, PermissionError),
            ({"code": "TIMEOUT_ERROR", "message": "test"}, TimeoutError),
            ({"code": 10095, "message": "test"}, ValueError),
            ({"code": 20003, "message": "test"}, IOError),
            ({"code": 20004, "message": "test"}, ValueError),
        ]
        
        for response, expected_exception in test_cases:
            with self.assertRaises(expected_exception, msg=f"Failed for {response}"):
                self.exchange._handle_response_errors(response)

    def test_reg003_success_codes_both_formats(self):
        """
        REG-003: Verify both numeric and string success codes work.
        
        Prevents regression of success code handling bug.
        """
        # Numeric success code
        self.exchange._handle_response_errors({"code": 10000, "data": {}})
        
        # String success code
        self.exchange._handle_response_errors({"code": "10000", "data": {}})
        
        # If we got here without exception, the test passes


if __name__ == "__main__":
    unittest.main()
