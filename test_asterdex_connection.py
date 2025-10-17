#!/usr/bin/env python3
"""
Test script to find the correct AsterDex API endpoints
"""
import asyncio
import aiohttp
import json

async def test_asterdex_connection():
    """Test different AsterDex API endpoint combinations"""
    print("=" * 80)
    print("TESTING ASTERDEX API ENDPOINTS")
    print("=" * 80)
    
    # Test different base URLs and endpoints
    test_combinations = [
        # Test 1: Standard API pattern
        ("https://api.asterdex.com/", "balance", "Standard API + balance"),
        ("https://api.asterdex.com/", "account", "Standard API + account"),
        
        # Test 2: With API version
        ("https://api.asterdex.com/api/v1/", "balance", "API v1 + balance"),
        ("https://api.asterdex.com/api/v1/", "account", "API v1 + account"),
        ("https://api.asterdex.com/api/v3/", "balance", "API v3 + balance"),
        ("https://api.asterdex.com/api/v3/", "account", "API v3 + account"),
        
        # Test 3: SAPI pattern
        ("https://sapi.asterdex.com/", "balance", "SAPI + balance"),
        ("https://sapi.asterdex.com/", "account", "SAPI + account"),
        ("https://sapi.asterdex.com/api/v1/", "balance", "SAPI v1 + balance"),
        ("https://sapi.asterdex.com/api/v3/", "account", "SAPI v3 + account"),
        
        # Test 4: Different balance endpoints
        ("https://api.asterdex.com/", "wallet/balance", "Standard + wallet/balance"),
        ("https://api.asterdex.com/", "user/balance", "Standard + user/balance"),
        ("https://api.asterdex.com/", "spot/balance", "Standard + spot/balance"),
        
        # Test 5: Ping endpoints to verify base URLs
        ("https://api.asterdex.com/", "ping", "Standard + ping"),
        ("https://sapi.asterdex.com/", "ping", "SAPI + ping"),
    ]
    
    async with aiohttp.ClientSession() as session:
        working_endpoints = []
        
        for base_url, endpoint, description in test_combinations:
            url = f"{base_url}{endpoint}"
            try:
                async with session.get(url, timeout=10) as response:
                    status = response.status
                    if status == 200:
                        print(f"✅ {description}: {url} (Status: {status})")
                        working_endpoints.append((base_url, endpoint, description))
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
    print("RESULTS SUMMARY")
    print("=" * 80)
    
    if working_endpoints:
        print("✅ Working endpoints found:")
        for base_url, endpoint, description in working_endpoints:
            print(f"   {base_url}{endpoint} - {description}")
        
        # Recommend the best configuration
        if any("ping" in desc for _, _, desc in working_endpoints):
            print("\n🎯 RECOMMENDED CONFIGURATION:")
            ping_endpoints = [(base, end, desc) for base, end, desc in working_endpoints if "ping" in desc]
            if ping_endpoints:
                base_url, _, _ = ping_endpoints[0]
                print(f"   Base URL: {base_url}")
                print(f"   Balance endpoint: 'balance' or 'account'")
    else:
        print("❌ No working endpoints found.")
        print("\n🔍 Possible issues:")
        print("   1. AsterDex API might be down")
        print("   2. Different base URL structure needed")
        print("   3. All endpoints require authentication")
        print("   4. API documentation might be outdated")
        print("   5. Network connectivity issues")

if __name__ == "__main__":
    asyncio.run(test_asterdex_connection())
