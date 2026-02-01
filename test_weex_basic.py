#!/usr/bin/env python3
"""
Basic test to see if WEEX connector can make API calls
"""
import asyncio
import sys
from pathlib import Path

from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange

# Add hummingbot to path (after imports)
sys.path.insert(0, str(Path(__file__).parent))


async def test_weex():
    print("Creating WEEX connector...")

    # Create connector with minimal config
    connector = WeexExchange(
        weex_api_key="test",  # Using dummy keys since we're only doing public calls
        weex_api_secret="test",
        weex_api_passphrase="",
        trading_pairs=["VCC-USDT"],
        trading_required=False,  # Read-only
    )

    print(f"Connector created: {connector}")
    print(f"Trading pairs: {connector.trading_pairs}")
    print(f"Is trading required: {connector.is_trading_required}")

    # Try to check network
    print("\nChecking network...")
    try:
        status = await connector.check_network()
        print(f"Network status: {status}")
    except Exception as e:
        print(f"Network check failed: {e}")
        import traceback
        traceback.print_exc()

    # Try to get trading pairs from exchange
    print("\nFetching trading pairs...")
    try:
        result = await connector._api_get(path_url="/api/v2/public/products")
        print(f"Got {len(result.get('data', []))} trading pairs")
        if 'VCCUSDT_SPBL' in result.get('data', []):
            print("✓ VCCUSDT_SPBL found!")
        else:
            print("✗ VCCUSDT_SPBL not found")
    except Exception as e:
        print(f"Failed to fetch trading pairs: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_weex())
