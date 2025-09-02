#!/usr/bin/env python3
"""
Test script to verify Polymarket connector connection and configuration.
Run this after setting up the connector to verify everything works.
"""

import asyncio
import sys
from pathlib import Path

# Add hummingbot to path
sys.path.append(str(Path(__file__).parent.parent))

from hummingbot.connector.event.polymarket.polymarket_auth import PolymarketAuth  # noqa: E402
from hummingbot.connector.event.polymarket.polymarket_event import PolymarketEvent  # noqa: E402


async def test_connection():
    """Test basic connection to Polymarket."""
    print("🧪 Testing Polymarket Connector Connection\n")

    # Test credentials - REPLACE WITH YOUR TEST CREDENTIALS
    PRIVATE_KEY = "0x0000000000000000000000000000000000000000000000000000000000000001"  # Replace  # noqa: mock
    WALLET_ADDRESS = "0x0000000000000000000000000000000000000001"  # Replace  # noqa: mock
    SIGNATURE_TYPE = 0  # EOA

    print("⚠️  Using test credentials - replace with your own for real testing\n")

    try:
        # Test 1: Authentication
        print("1️⃣ Testing Authentication...")
        auth = PolymarketAuth(
            private_key=PRIVATE_KEY,
            wallet_address=WALLET_ADDRESS,
            signature_type=SIGNATURE_TYPE
        )
        await auth.ensure_initialized()
        print("✅ Authentication initialized\n")

        # Test 2: Connector Creation
        print("2️⃣ Creating Connector...")
        connector = PolymarketEvent(
            polymarket_private_key=PRIVATE_KEY,
            polymarket_wallet_address=WALLET_ADDRESS,
            polymarket_signature_type=SIGNATURE_TYPE,
            trading_pairs=["ELECTION2024-YES-USDC"],
            trading_required=True
        )
        print("✅ Connector created\n")

        # Test 3: Fetch Markets
        print("3️⃣ Fetching Active Markets...")
        markets = await connector.get_active_markets()
        print("✅ Found {} active markets".format(len(markets)))
        if markets:
            print("   Sample: {}\n".format(markets[0].market_id if markets else 'None'))

        # Test 4: Check Balances
        print("4️⃣ Checking Account Balances...")
        balances = await connector.get_account_balances()
        print("✅ Balances retrieved")
        for asset, balance in balances.items():
            print("   {}: {}".format(asset, balance))

        print("\n🎉 All connection tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_connection())
    sys.exit(0 if result else 1)
