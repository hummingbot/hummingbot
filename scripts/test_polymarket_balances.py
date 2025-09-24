#!/usr/bin/env python3
"""
Test script for Polymarket balance operations.
Fetches and displays account balances and positions.
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

# Add hummingbot to path
sys.path.append(str(Path(__file__).parent.parent))

from hummingbot.connector.event.polymarket.polymarket_api_data_source import PolymarketAPIDataSource  # noqa: E402
from hummingbot.connector.event.polymarket.polymarket_auth import PolymarketAuth  # noqa: E402


async def test_balances():
    """Test balance fetching from Polymarket."""
    print("🧪 Testing Polymarket Balance Operations\n")

    # Test credentials - REPLACE WITH YOUR TEST CREDENTIALS
    PRIVATE_KEY = "0x0000000000000000000000000000000000000000000000000000000000000001"  # Replace  # noqa: mock
    WALLET_ADDRESS = "0x0000000000000000000000000000000000000001"  # Replace  # noqa: mock
    SIGNATURE_TYPE = 0  # EOA

    print("⚠️  Using test credentials - replace with your own for real testing\n")

    try:
        # Initialize auth
        print("🔐 Initializing authentication...")
        auth = PolymarketAuth(
            private_key=PRIVATE_KEY,
            wallet_address=WALLET_ADDRESS,
            signature_type=SIGNATURE_TYPE
        )
        await auth.ensure_initialized()
        print("✅ Authentication ready\n")

        # Initialize API data source
        print("📊 Creating API data source...")
        api_source = PolymarketAPIDataSource(
            trading_pairs=["ELECTION2024-YES-USDC"],
            auth=auth
        )
        print("✅ API data source ready\n")

        # Test 1: Fetch USDC Balance
        print("1️⃣ Fetching Account Balances...")
        balances = await api_source.get_account_balances()
        print("✅ Balances retrieved:")

        total_value = Decimal("0")
        for asset, balance in balances.items():
            print("   {:10s}: {:>15.4f}".format(asset, balance))
            if asset == "USDC":
                total_value += balance

        print(f"\n   {'Total USDC':10s}: {total_value:>15.4f}\n")

        # Test 2: Fetch Positions
        print("2️⃣ Fetching Account Positions...")
        positions = await api_source.get_account_positions()
        print("✅ Found {} positions".format(len(positions)))

        if positions:
            print("\n   Market Positions:")
            for pos in positions[:5]:  # Show first 5
                print("   - Market: {}".format(pos.market_id))
                print("     Outcome: {}".format(pos.outcome.name))
                print("     Size: {}".format(pos.size))
                print("     Entry Price: {}".format(pos.entry_price))
                print("     Current Price: {}".format(pos.current_price))
                print("     PnL: {}".format(pos.unrealized_pnl))
                print()
        else:
            print("   No open positions\n")

        # Test 3: Calculate Portfolio Value
        print("3️⃣ Portfolio Summary:")
        print("   USDC Balance: {:.4f}".format(balances.get("USDC", Decimal("0"))))
        print("   Open Positions: {}".format(len(positions)))

        position_value = sum(pos.size * pos.current_price for pos in positions)
        print("   Position Value: {:.4f} USDC".format(position_value))
        print("   Total Value: {:.4f} USDC".format(balances.get("USDC", Decimal("0")) + position_value))

        print("\n🎉 Balance tests completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Balance test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_balances())
    sys.exit(0 if result else 1)
