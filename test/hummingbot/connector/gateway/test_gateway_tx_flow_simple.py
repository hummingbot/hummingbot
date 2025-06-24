#!/usr/bin/env python
"""
Simplified test for Gateway transaction flow with fee retry logic.
This test focuses on the core logic without complex imports.
"""

import asyncio
import time
import unittest
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock


class MockGatewayTxHandler:
    """Simplified version of GatewayHttpClient for testing"""

    def __init__(self, connector_name: str, chain: str, network: str):
        self.connector_name = connector_name
        self.chain = chain
        self.network = network

        # Configuration
        self.base_fee_per_cu = 500_000  # microlamports
        self.priority_fee_multiplier = 2.0
        self.min_fee_per_cu = 100_000
        self.max_fee_per_cu = 10_000_000
        self.max_retries = 3
        self.fee_estimate_cache_interval = 60  # seconds

        # Caches
        self._compute_units_cache: Dict[str, int] = {}
        self._fee_estimate_cache: Dict[str, tuple] = {}  # {key: (fee_per_cu, timestamp)}

        # Mock gateway client
        self.gateway = AsyncMock()

    def _get_cache_key(self, tx_type: str) -> str:
        """Generate cache key for transaction type"""
        return f"{tx_type}:{self.chain}:{self.network}"

    async def get_fee_estimate(self) -> int:
        """Get current fee estimate from Gateway"""
        cache_key = f"fee_estimate:{self.chain}:{self.network}"

        # Check cache
        if cache_key in self._fee_estimate_cache:
            fee_per_cu, timestamp = self._fee_estimate_cache[cache_key]
            if time.time() - timestamp < self.fee_estimate_cache_interval:
                return fee_per_cu

        # Fetch from Gateway
        response = await self.gateway.estimate_gas(self.chain, self.network)
        fee_per_cu = int(response["feePerComputeUnit"])

        # Cache the result
        self._fee_estimate_cache[cache_key] = (fee_per_cu, time.time())

        return fee_per_cu

    def get_cached_compute_units(self, tx_type: str) -> Optional[int]:
        """Get cached compute units for transaction type"""
        cache_key = self._get_cache_key(tx_type)
        return self._compute_units_cache.get(cache_key)

    def cache_compute_units(self, tx_type: str, compute_units: int):
        """Cache compute units for transaction type"""
        cache_key = self._get_cache_key(tx_type)
        self._compute_units_cache[cache_key] = compute_units

    async def execute_transaction_with_retry(
        self,
        tx_type: str,
        execute_fn: callable,
        base_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute transaction with fee retry logic"""

        # Get or estimate compute units
        compute_units = self.get_cached_compute_units(tx_type)
        if compute_units is None:
            # Use default based on transaction type
            if "swap" in tx_type:
                compute_units = 600_000
            else:
                compute_units = 800_000

        # Get current fee estimate
        estimated_fee_per_cu = await self.get_fee_estimate()

        for attempt in range(self.max_retries + 1):
            # Calculate priority fee with multiplier
            multiplier = self.priority_fee_multiplier ** attempt
            current_priority_fee_per_cu = int(estimated_fee_per_cu * multiplier)

            # Apply bounds
            current_priority_fee_per_cu = max(
                self.min_fee_per_cu,
                min(current_priority_fee_per_cu, self.max_fee_per_cu)
            )

            # Prepare parameters
            params = {
                **base_params,
                "priorityFeePerCU": current_priority_fee_per_cu,
                "computeUnits": compute_units
            }

            print(f"Attempt {attempt + 1}: Executing with fee {current_priority_fee_per_cu} microlamports/CU")

            try:
                # Execute transaction
                result = await execute_fn(**params)

                # Check if transaction succeeded
                if result.get("status") == 1:  # CONFIRMED
                    print(f"Transaction confirmed: {result['signature']}")

                    # Cache compute units from quote if available
                    if "computeUnits" in base_params:
                        self.cache_compute_units(tx_type, base_params["computeUnits"])

                    return result
                elif result.get("status") == -1:  # FAILED
                    error_msg = result.get("error", "Unknown error")

                    # Check if it's a fee-related error
                    if "insufficient" in error_msg.lower() or "fee" in error_msg.lower():
                        print("Transaction failed due to insufficient fee, retrying...")
                        continue
                    else:
                        # Non-fee error, don't retry
                        raise Exception(f"Transaction failed: {error_msg}")

            except Exception as e:
                print(f"Error executing transaction: {e}")
                if attempt == self.max_retries:
                    raise

        # Exhausted all retries
        raise Exception(f"Transaction failed after {self.max_retries + 1} attempts")


class TestGatewayTxFlow(unittest.TestCase):
    """Test Gateway transaction flow with fee retry logic"""

    def setUp(self):
        self.tx_handler = MockGatewayTxHandler(
            connector_name="raydium",
            chain="solana",
            network="mainnet-beta"
        )

    async def async_test_successful_sell_first_attempt(self):
        """Test successful SELL order on first attempt"""

        # Mock estimate gas response
        self.tx_handler.gateway.estimate_gas.return_value = {
            "feePerComputeUnit": 500_000,
            "denomination": "microlamports",
            "timestamp": int(time.time() * 1000)
        }

        # Mock successful execute swap response
        async def mock_execute_swap(**kwargs):
            return {
                "signature": "5TBLtTe9wvG69kitNrpETAjjNmTw3dWcwWxGsWyNvBecPHkrZTgBaPQJMCb89v9FL9b33U3Pd9iW1trDvvbDpJCK",
                "status": 1,  # CONFIRMED
                "data": {
                    "totalInputSwapped": 0.010605,
                    "totalOutputSwapped": 1.5375319999999988,
                    "fee": 0.000605,
                    "baseTokenBalanceChange": -0.010605,
                    "quoteTokenBalanceChange": 1.5375319999999988
                }
            }

        base_params = {
            "network": "mainnet-beta",
            "walletAddress": "82SggYRE2Vo4jN4a2pk3aQ4SET4ctafZJGbowmCqyHx5",
            "baseToken": "SOL",
            "quoteToken": "USDC",
            "amount": 0.01,
            "side": "SELL",
            "slippagePct": 1,
            "computeUnits": 600_000  # From quote
        }

        result = await self.tx_handler.execute_transaction_with_retry(
            tx_type="swap",
            execute_fn=mock_execute_swap,
            base_params=base_params
        )

        # Verify result
        self.assertEqual(result["status"], 1)
        self.assertEqual(result["signature"], "5TBLtTe9wvG69kitNrpETAjjNmTw3dWcwWxGsWyNvBecPHkrZTgBaPQJMCb89v9FL9b33U3Pd9iW1trDvvbDpJCK")
        self.assertEqual(result["data"]["totalInputSwapped"], 0.010605)

        # Verify compute units were cached
        self.assertEqual(self.tx_handler.get_cached_compute_units("swap"), 600_000)

    async def async_test_buy_with_fee_retry(self):
        """Test BUY order that requires fee retry"""

        # Mock estimate gas response
        self.tx_handler.gateway.estimate_gas.return_value = {
            "feePerComputeUnit": 100_000,  # Low initial estimate
            "denomination": "microlamports",
            "timestamp": int(time.time() * 1000)
        }

        # Track attempts
        attempt_count = 0

        async def mock_execute_swap(**kwargs):
            nonlocal attempt_count
            attempt_count += 1

            # Fail first two attempts due to insufficient fee
            if attempt_count < 3:
                return {
                    "signature": f"failed_sig_{attempt_count}",
                    "status": -1,  # FAILED
                    "error": "Transaction failed: insufficient priority fee"
                }
            else:
                # Succeed on third attempt
                return {
                    "signature": "45eeF7L7qZmWANgud8YNnwwLkJ2uZoWqZaMuNCzpUSX9qMyqrkBx2jV9LfMqWJzR5rVYhUbpFTeWvyHAg94BUSQQ",
                    "status": 1,  # CONFIRMED
                    "data": {
                        "totalInputSwapped": 0.009395,
                        "totalOutputSwapped": 1.539718999999998,
                        "fee": 0.000605,
                        "baseTokenBalanceChange": 0.009395,
                        "quoteTokenBalanceChange": -1.539718999999998
                    }
                }

        base_params = {
            "network": "mainnet-beta",
            "walletAddress": "82SggYRE2Vo4jN4a2pk3aQ4SET4ctafZJGbowmCqyHx5",
            "baseToken": "SOL",
            "quoteToken": "USDC",
            "amount": 0.01,
            "side": "BUY",
            "slippagePct": 1
        }

        result = await self.tx_handler.execute_transaction_with_retry(
            tx_type="swap",
            execute_fn=mock_execute_swap,
            base_params=base_params
        )

        # Verify result
        self.assertEqual(result["status"], 1)
        self.assertEqual(attempt_count, 3)  # Should have taken 3 attempts
        self.assertEqual(result["signature"], "45eeF7L7qZmWANgud8YNnwwLkJ2uZoWqZaMuNCzpUSX9qMyqrkBx2jV9LfMqWJzR5rVYhUbpFTeWvyHAg94BUSQQ")

    async def async_test_max_retries_exceeded(self):
        """Test transaction that fails after max retries"""

        # Mock estimate gas response
        self.tx_handler.gateway.estimate_gas.return_value = {
            "feePerComputeUnit": 100_000,
            "denomination": "microlamports",
            "timestamp": int(time.time() * 1000)
        }

        # Always fail
        async def mock_execute_swap(**kwargs):
            return {
                "signature": "failed_sig",
                "status": -1,  # FAILED
                "error": "Transaction failed: insufficient priority fee"
            }

        base_params = {
            "network": "mainnet-beta",
            "walletAddress": "82SggYRE2Vo4jN4a2pk3aQ4SET4ctafZJGbowmCqyHx5",
            "baseToken": "SOL",
            "quoteToken": "USDC",
            "amount": 0.01,
            "side": "SELL",
            "slippagePct": 1
        }

        with self.assertRaises(Exception) as context:
            await self.tx_handler.execute_transaction_with_retry(
                tx_type="swap",
                execute_fn=mock_execute_swap,
                base_params=base_params
            )

        self.assertIn("failed after 4 attempts", str(context.exception))

    async def async_test_fee_bounds_enforcement(self):
        """Test that fees are properly bounded"""

        # Set very high initial estimate
        self.tx_handler.gateway.estimate_gas.return_value = {
            "feePerComputeUnit": 20_000_000,  # Very high
            "denomination": "microlamports",
            "timestamp": int(time.time() * 1000)
        }

        fees_used = []

        async def mock_execute_swap(**kwargs):
            fees_used.append(kwargs["priorityFeePerCU"])
            return {
                "signature": "failed_sig",
                "status": -1,
                "error": "insufficient fee"
            }

        base_params = {
            "network": "mainnet-beta",
            "walletAddress": "test_wallet",
            "baseToken": "SOL",
            "quoteToken": "USDC",
            "amount": 0.01,
            "side": "SELL"
        }

        try:
            await self.tx_handler.execute_transaction_with_retry(
                tx_type="swap",
                execute_fn=mock_execute_swap,
                base_params=base_params
            )
        except Exception:
            pass  # Expected to fail

        # Verify all fees were bounded by max_fee_per_cu
        for fee in fees_used:
            self.assertLessEqual(fee, self.tx_handler.max_fee_per_cu)
            self.assertGreaterEqual(fee, self.tx_handler.min_fee_per_cu)

    def test_successful_sell_first_attempt(self):
        """Sync wrapper for async test"""
        asyncio.run(self.async_test_successful_sell_first_attempt())

    def test_buy_with_fee_retry(self):
        """Sync wrapper for async test"""
        asyncio.run(self.async_test_buy_with_fee_retry())

    def test_max_retries_exceeded(self):
        """Sync wrapper for async test"""
        asyncio.run(self.async_test_max_retries_exceeded())

    def test_fee_bounds_enforcement(self):
        """Sync wrapper for async test"""
        asyncio.run(self.async_test_fee_bounds_enforcement())


if __name__ == "__main__":
    # Run tests
    print("Testing Gateway Transaction Flow with Fee Retry Logic")
    print("=" * 60)

    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGatewayTxFlow)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 60)
    if result.wasSuccessful():
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
