#!/usr/bin/env python3
"""
Final test script for AsterDex API endpoints
"""
import asyncio
import aiohttp
import sys
import os

# Add the hummingbot directory to the path
sys.path.insert(0, '/Users/massloreti/hummingbot')

async def test_asterdex_api():
    """Test AsterDex API endpoints"""
    print("=" * 80)
    print("TESTING ASTERDEX API ENDPOINTS")
    print("=" * 80)
    
    # Test the corrected endpoints
    test_endpoints = [
        ("https://fapi.asterdex.com/api/v3/ping", "Ping endpoint"),
        ("https://fapi.asterdex.com/api/v3/exchangeInfo", "Exchange info"),
        ("https://fapi.asterdex.com/api/v3/account", "Account (requires auth)"),
    ]
    
    async with aiohttp.ClientSession() as session:
        for url, description in test_endpoints:
            try:
                async with session.get(url, timeout=10) as response:
                    status = response.status
                    if status == 200:
                        print(f"✅ {description}: {url} (Status: {status})")
                        if "ping" in url:
                            text = await response.text()
                            print(f"   Response: {text[:100]}")
                    elif status == 404:
                        print(f"❌ {description}: {url} (Status: {status} - Not Found)")
                    elif status == 401:
                        print(f"🔐 {description}: {url} (Status: {status} - Auth Required)")
                    elif status == 403:
                        print(f"🚫 {description}: {url} (Status: {status} - Forbidden)")
                    else:
                        print(f"⚠️  {description}: {url} (Status: {status})")
            except Exception as e:
                print(f"💥 {description}: {url} (Error: {e})")
    
    print("\n" + "=" * 80)
    print("TESTING ASTERDEX CONNECTOR")
    print("=" * 80)
    
    try:
        from hummingbot.connector.exchange.asterdex.asterdex_exchange import AsterdexExchange
        
        # Create exchange instance
        exchange = AsterdexExchange(
            asterdex_api_key="test_key",
            asterdex_secret_key="test_secret",
            trading_pairs=[],
            trading_required=False
        )
        
        print(f"✅ AsterDex exchange created successfully")
        print(f"   Public URL: {exchange._api_factory._public_rest_url}")
        print(f"   Private URL: {exchange._api_factory._private_rest_url}")
        print(f"   Balance endpoint: {exchange._api_factory._private_rest_url}account")
        
    except Exception as e:
        print(f"❌ Error creating AsterDex exchange: {e}")

if __name__ == "__main__":
    asyncio.run(test_asterdex_api())
