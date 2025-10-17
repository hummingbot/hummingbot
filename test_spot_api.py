#!/usr/bin/env python3
"""
Test script to verify AsterDex spot API connection
"""
import asyncio
import sys
import os

# Add the hummingbot directory to the path
sys.path.insert(0, '/Users/massloreti/hummingbot')

from hummingbot.connector.exchange.asterdex.asterdex_exchange import AsterdexExchange

async def test_spot_connection():
    """Test the AsterDex spot API connection"""
    print("=" * 60)
    print("TESTING ASTERDEX SPOT API CONNECTION")
    print("=" * 60)
    
    # Create exchange instance with spot API
    exchange = AsterdexExchange(
        asterdex_api_key="test_key",
        asterdex_secret_key="test_secret", 
        trading_pairs=[],
        trading_required=False
    )
    
    print(f"✅ Exchange created with spot API endpoints")
    print(f"   Public URL: {exchange._api_factory._public_rest_url}")
    print(f"   Private URL: {exchange._api_factory._private_rest_url}")
    print(f"   WebSocket URL: {exchange._api_factory._ws_url}")
    
    # Test exchange info endpoint
    try:
        print("\n🔍 Testing exchange info endpoint...")
        exchange_info = await exchange._api_request("GET", exchange.trading_rules_request_path)
        print(f"✅ Exchange info response type: {type(exchange_info)}")
        print(f"✅ Exchange info length: {len(exchange_info) if hasattr(exchange_info, '__len__') else 'N/A'}")
        
        if isinstance(exchange_info, list):
            print(f"✅ Got list response with {len(exchange_info)} items")
            if exchange_info:
                print(f"✅ First item: {exchange_info[0]}")
        elif isinstance(exchange_info, dict):
            print(f"✅ Got dict response with keys: {list(exchange_info.keys())}")
        else:
            print(f"⚠️  Unexpected response type: {type(exchange_info)}")
            
    except Exception as e:
        print(f"❌ Error testing exchange info: {e}")
        return False
    
    print("\n✅ AsterDex spot API connection test completed successfully!")
    return True

if __name__ == "__main__":
    asyncio.run(test_spot_connection())
