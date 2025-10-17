#!/usr/bin/env python3
"""
Test script to find the correct AsterDex spot API endpoints
"""
import asyncio
import aiohttp
import sys

async def test_endpoint(session, base_url, endpoint, description):
    """Test a specific endpoint"""
    url = f"{base_url}{endpoint}"
    try:
        async with session.get(url, timeout=10) as response:
            status = response.status
            if status == 200:
                print(f"✅ {description}: {url} (Status: {status})")
                return True
            elif status == 404:
                print(f"❌ {description}: {url} (Status: {status} - Not Found)")
            elif status == 401:
                print(f"🔐 {description}: {url} (Status: {status} - Auth Required)")
            else:
                print(f"⚠️  {description}: {url} (Status: {status})")
    except Exception as e:
        print(f"💥 {description}: {url} (Error: {e})")
    return False

async def test_asterdex_endpoints():
    """Test various AsterDex API endpoint combinations"""
    print("=" * 80)
    print("TESTING ASTERDEX SPOT API ENDPOINTS")
    print("=" * 80)
    
    # Test different base URLs and endpoints
    test_cases = [
        # Base URL variations
        ("https://sapi.asterdex.com/", "balance", "Direct balance endpoint"),
        ("https://sapi.asterdex.com/api/", "balance", "API v1 balance"),
        ("https://sapi.asterdex.com/api/v1/", "balance", "API v1 balance"),
        ("https://sapi.asterdex.com/api/v3/", "balance", "API v3 balance"),
        
        # Different balance endpoint variations
        ("https://sapi.asterdex.com/api/v1/", "account", "Account endpoint"),
        ("https://sapi.asterdex.com/api/v1/", "wallet/balance", "Wallet balance"),
        ("https://sapi.asterdex.com/api/v1/", "user/balance", "User balance"),
        ("https://sapi.asterdex.com/api/v1/", "spot/balance", "Spot balance"),
        
        # Test ping endpoint
        ("https://sapi.asterdex.com/", "ping", "Ping endpoint"),
        ("https://sapi.asterdex.com/api/v1/", "ping", "API v1 ping"),
        ("https://sapi.asterdex.com/api/v3/", "ping", "API v3 ping"),
        
        # Test exchange info
        ("https://sapi.asterdex.com/api/v1/", "exchangeInfo", "Exchange info v1"),
        ("https://sapi.asterdex.com/api/v3/", "exchangeInfo", "Exchange info v3"),
    ]
    
    async with aiohttp.ClientSession() as session:
        working_endpoints = []
        
        for base_url, endpoint, description in test_cases:
            success = await test_endpoint(session, base_url, endpoint, description)
            if success:
                working_endpoints.append((base_url, endpoint, description))
    
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    
    if working_endpoints:
        print("✅ Working endpoints found:")
        for base_url, endpoint, description in working_endpoints:
            print(f"   {base_url}{endpoint} - {description}")
    else:
        print("❌ No working endpoints found. Possible issues:")
        print("   1. AsterDex API might be down")
        print("   2. Different base URL structure needed")
        print("   3. Authentication required for all endpoints")
        print("   4. API documentation might be outdated")

if __name__ == "__main__":
    asyncio.run(test_asterdex_endpoints())
