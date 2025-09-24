#!/usr/bin/env python3
"""
Test script for Polymarket trading operations.
Tests order placement, cancellation, and tracking.
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

# Add hummingbot to path
sys.path.append(str(Path(__file__).parent.parent))

from hummingbot.connector.event.polymarket.polymarket_event import PolymarketEvent  # noqa: E402
from hummingbot.core.data_type.common import OrderType, OutcomeType, TradeType  # noqa: E402


async def test_trading():
    """Test trading operations on Polymarket."""
    print("🧪 Testing Polymarket Trading Operations\n")

    # Test credentials - REPLACE WITH YOUR TEST CREDENTIALS
    PRIVATE_KEY = "0x0000000000000000000000000000000000000000000000000000000000000001"  # Replace  # noqa: mock
    WALLET_ADDRESS = "0x0000000000000000000000000000000000000001"  # Replace  # noqa: mock
    SIGNATURE_TYPE = 0  # EOA

    # Test market - REPLACE WITH ACTUAL MARKET
    TEST_MARKET = "ELECTION2024"  # Replace with real market ID
    TEST_OUTCOME = OutcomeType.YES
    TEST_AMOUNT = Decimal("1.0")  # Small test amount
    TEST_PRICE = Decimal("0.50")  # 50 cents

    print("⚠️  Using test parameters - adjust for your testing needs\n")

    try:
        # Initialize connector
        print("📡 Initializing connector...")
        connector = PolymarketEvent(
            polymarket_private_key=PRIVATE_KEY,
            polymarket_wallet_address=WALLET_ADDRESS,
            polymarket_signature_type=SIGNATURE_TYPE,
            trading_pairs=[f"{TEST_MARKET}-{TEST_OUTCOME.name}-USDC"],
            trading_required=True
        )
        print("✅ Connector initialized\n")

        # Test 1: Place Limit Order
        print("1️⃣ Placing Test Limit Order...")
        print("   Market: {}".format(TEST_MARKET))
        print("   Outcome: {}".format(TEST_OUTCOME.name))
        print("   Type: BUY")
        print("   Amount: {}".format(TEST_AMOUNT))
        print("   Price: {}".format(TEST_PRICE))

        order_id = await connector.place_prediction_order(
            market_id=TEST_MARKET,
            outcome=TEST_OUTCOME,
            trade_type=TradeType.BUY,
            amount=TEST_AMOUNT,
            price=TEST_PRICE,
            order_type=OrderType.LIMIT
        )
        print(f"✅ Order placed with ID: {order_id}\n")

        # Wait a moment for order to process
        await asyncio.sleep(2)

        # Test 2: Check Order Status
        print("2️⃣ Checking Order Status...")
        tracked_order = connector._order_tracker.fetch_order(order_id)
        if tracked_order:
            print("✅ Order found in tracker")
            print("   Status: {}".format(tracked_order.current_state))
            print(f"   Exchange ID: {tracked_order.exchange_order_id}\n")
        else:
            print("⚠️  Order not found in tracker\n")

        # Test 3: Cancel Order
        print("3️⃣ Cancelling Test Order...")
        if tracked_order:
            success = await connector._cancel_event_order(order_id)
            if success:
                print("✅ Order cancelled successfully\n")
            else:
                print("⚠️  Order cancellation failed\n")

        # Test 4: Check Active Orders
        print("4️⃣ Checking Active Orders...")
        active_orders = connector._order_tracker.active_orders
        print(f"✅ Active orders: {len(active_orders)}")
        for order_id, order in active_orders.items():
            print(f"   {order_id}: {order.trading_pair} - {order.amount} @ {order.price}")

        print("\n🎉 Trading tests completed!")
        return True

    except Exception as e:
        print(f"\n❌ Trading test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_trading())
    sys.exit(0 if result else 1)
