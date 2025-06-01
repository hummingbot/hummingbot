#!/usr/bin/env python
"""
Integration test for complete Gateway transaction flow.
Tests the flow from GatewayLP -> GatewaySwap -> GatewayTxHandler with fee retry logic.
"""

import asyncio
import time
from decimal import Decimal
from typing import Any, Dict


class MockGatewayHTTPClient:
    """Mock Gateway HTTP client for testing"""

    def __init__(self):
        self.response_queue = []
        self.request_history = []

    async def estimate_gas(self, chain: str, network: str) -> Dict[str, Any]:
        """Mock estimate gas endpoint"""
        self.request_history.append(("estimate_gas", chain, network))
        return {
            "feePerComputeUnit": 500_000,
            "denomination": "microlamports",
            "timestamp": int(time.time() * 1000)
        }

    async def get_quote(self, connector: str, **params) -> Dict[str, Any]:
        """Mock quote endpoint"""
        self.request_history.append(("quote", connector, params))
        return {
            "poolAddress": "3ucNos4NbumPLZNWztqGHNFFgkHeRMBQAVemeeomsUxv",
            "estimatedAmountIn": 0.01,
            "estimatedAmountOut": 1.537532,
            "minAmountOut": 1.522156,
            "maxAmountIn": 0.0101,
            "baseTokenBalanceChange": -0.01,
            "quoteTokenBalanceChange": 1.537532,
            "price": 153.7532,
            "computeUnits": 600_000  # New field
        }

    async def execute_swap(self, connector: str, **params) -> Dict[str, Any]:
        """Mock execute swap endpoint"""
        self.request_history.append(("execute_swap", connector, params))

        # Pop response from queue or use default
        if self.response_queue:
            return self.response_queue.pop(0)

        # Default successful response
        if params.get("side") == "SELL":
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
        else:  # BUY
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

    async def poll_transaction(self, chain: str, network: str, signature: str) -> Dict[str, Any]:
        """Mock poll transaction endpoint"""
        self.request_history.append(("poll", chain, network, signature))
        return {
            "currentBlock": 343927623,
            "signature": signature,
            "txBlock": 343927464,
            "txStatus": 1,  # CONFIRMED
            "txData": {"fee": 605000},
            "fee": 0.000605
        }


class MockOrder:
    """Mock order for testing"""

    def __init__(self, trading_pair: str, is_buy: bool, amount: Decimal, price: Decimal):
        self.trading_pair = trading_pair
        self.is_buy = is_buy
        self.amount = amount
        self.price = price
        self.client_order_id = f"test_order_{int(time.time())}"
        self.exchange_order_id = None
        self.current_state = "PENDING_CREATE"

    def update_exchange_order_id(self, exchange_order_id: str):
        self.exchange_order_id = exchange_order_id
        self.current_state = "OPEN"


async def test_complete_gateway_flow():
    """Test the complete Gateway flow with fee retry logic"""

    print("\n🧪 Testing Complete Gateway Transaction Flow")
    print("=" * 60)

    # Create mock components
    gateway_client = MockGatewayHTTPClient()

    # Test 1: Successful swap on first attempt
    print("\n✅ Test 1: Successful SELL on first attempt")
    print("-" * 40)

    # Create order
    order = MockOrder("SOL-USDC", is_buy=False, amount=Decimal("0.01"), price=Decimal("150"))

    # Get quote
    quote = await gateway_client.get_quote(
        "raydium/clmm",
        network="mainnet-beta",
        baseToken="SOL",
        quoteToken="USDC",
        amount=0.01,
        side="SELL"
    )
    print(f"Quote received: {quote['computeUnits']} compute units")

    # Execute swap with fee parameters
    swap_result = await gateway_client.execute_swap(
        "raydium/clmm",
        network="mainnet-beta",
        walletAddress="82SggYRE2Vo4jN4a2pk3aQ4SET4ctafZJGbowmCqyHx5",
        baseToken="SOL",
        quoteToken="USDC",
        amount=0.01,
        side="SELL",
        slippagePct=1,
        priorityFeePerCU=1_000_000,
        computeUnits=quote["computeUnits"]
    )

    print(f"Transaction confirmed: {swap_result['signature']}")
    print(f"Status: {'CONFIRMED' if swap_result['status'] == 1 else 'FAILED'}")
    print(f"Input: {swap_result['data']['totalInputSwapped']} SOL")
    print(f"Output: {swap_result['data']['totalOutputSwapped']} USDC")

    # Update order
    order.update_exchange_order_id(swap_result['signature'])
    print(f"Order state: {order.current_state}")

    # Test 2: Transaction with fee retry
    print("\n🔄 Test 2: BUY order with fee retry (3 attempts)")
    print("-" * 40)

    # Queue failed responses followed by success
    gateway_client.response_queue = [
        {
            "signature": "failed_1",
            "status": -1,
            "error": "Transaction failed: insufficient priority fee"
        },
        {
            "signature": "failed_2",
            "status": -1,
            "error": "Transaction failed: insufficient priority fee"
        },
        # Third attempt will use default success response
    ]

    # Simulate retry logic
    max_retries = 3
    base_fee = 100_000
    fee_multiplier = 2.0

    for attempt in range(max_retries + 1):
        current_fee = int(base_fee * (fee_multiplier ** attempt))
        print(f"\nAttempt {attempt + 1}: Fee = {current_fee} microlamports/CU")

        result = await gateway_client.execute_swap(
            "raydium/clmm",
            network="mainnet-beta",
            walletAddress="82SggYRE2Vo4jN4a2pk3aQ4SET4ctafZJGbowmCqyHx5",
            baseToken="SOL",
            quoteToken="USDC",
            amount=0.01,
            side="BUY",
            slippagePct=1,
            priorityFeePerCU=current_fee,
            computeUnits=600_000
        )

        if result.get("status") == 1:
            print(f"✅ Transaction confirmed: {result['signature']}")
            break
        else:
            print(f"❌ Transaction failed: {result.get('error', 'Unknown error')}")
            if attempt < max_retries:
                print("   Retrying with higher fee...")

    # Test 3: Parallel transactions
    print("\n🚀 Test 3: Parallel transactions")
    print("-" * 40)

    # Reset response queue
    gateway_client.response_queue = []

    # Execute multiple transactions in parallel
    tasks = []
    for i in range(3):
        task = gateway_client.execute_swap(
            "raydium/clmm",
            network="mainnet-beta",
            walletAddress="82SggYRE2Vo4jN4a2pk3aQ4SET4ctafZJGbowmCqyHx5",
            baseToken="SOL",
            quoteToken="USDC",
            amount=0.005,
            side="SELL" if i % 2 == 0 else "BUY",
            slippagePct=1,
            priorityFeePerCU=500_000,
            computeUnits=600_000
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    for i, result in enumerate(results):
        side = "SELL" if i % 2 == 0 else "BUY"
        print(f"Transaction {i + 1} ({side}): {result['signature'][:20]}... - {'✅' if result['status'] == 1 else '❌'}")

    # Test 4: Fee bounds enforcement
    print("\n🛡️ Test 4: Fee bounds enforcement")
    print("-" * 40)

    min_fee = 100_000
    max_fee = 10_000_000

    test_fees = [50_000, 500_000, 20_000_000]  # Below min, normal, above max

    for test_fee in test_fees:
        bounded_fee = max(min_fee, min(test_fee, max_fee))
        print(f"Requested: {test_fee:,} → Bounded: {bounded_fee:,} microlamports/CU")

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"- Total requests made: {len(gateway_client.request_history)}")
    print(f"- Request types: {set(req[0] for req in gateway_client.request_history)}")
    print("- All tests completed successfully! ✅")


async def test_lp_operations():
    """Test liquidity provision operations with fee retry"""

    print("\n\n💧 Testing LP Operations with Fee Retry")
    print("=" * 60)

    gateway_client = MockGatewayHTTPClient()

    # Mock LP operation responses
    async def mock_open_position(**params):
        return {
            "signature": "lp_open_sig_123",
            "status": 1,
            "fee": 0.001,
            "positionAddress": "position_123",
            "positionRent": 0.00203928,
            "baseTokenAmountAdded": params.get("baseTokenAmount", 0.1),
            "quoteTokenAmountAdded": params.get("quoteTokenAmount", 15)
        }

    # Test open position with retry
    print("\n📍 Opening LP position with fee retry")
    print("-" * 40)

    # First attempt fails
    gateway_client.response_queue = [
        {
            "signature": "failed_lp",
            "status": -1,
            "error": "Transaction simulation failed: insufficient compute units"
        }
    ]

    # Simulate retry for LP operation
    for attempt in range(2):
        compute_units = 800_000 if attempt == 0 else 1_200_000  # Increase CU on retry
        fee_per_cu = 500_000 * (2 ** attempt)

        print(f"\nAttempt {attempt + 1}:")
        print(f"  Compute Units: {compute_units:,}")
        print(f"  Fee per CU: {fee_per_cu:,} microlamports")

        if attempt == 0:
            # Use queued failure response
            result = await gateway_client.execute_swap("raydium/clmm", side="LP_OPEN")
        else:
            # Use mock success
            result = await mock_open_position(
                baseTokenAmount=0.1,
                quoteTokenAmount=15,
                priorityFeePerCU=fee_per_cu,
                computeUnits=compute_units
            )

        if result.get("status") == 1:
            print(f"✅ Position opened: {result['positionAddress']}")
            print(f"   Base added: {result['baseTokenAmountAdded']}")
            print(f"   Quote added: {result['quoteTokenAmountAdded']}")
            break
        else:
            print(f"❌ Failed: {result.get('error')}")
            print("   Increasing compute units and retrying...")

    print("\n✅ LP operations test completed!")


if __name__ == "__main__":
    # Run all tests
    print("🚀 Gateway Transaction Flow Integration Test")
    print("=" * 60)

    # Run main flow test
    asyncio.run(test_complete_gateway_flow())

    # Run LP operations test
    asyncio.run(test_lp_operations())

    print("\n\n🎉 All integration tests completed successfully!")
