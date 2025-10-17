#!/usr/bin/env python3
"""
Test Extended API authentication to debug 401 errors
"""
import asyncio
import aiohttp

async def test_extended_api(api_key: str):
    """Test Extended API endpoints to diagnose 401 issues"""
    
    base_url = "https://api.starknet.extended.exchange"
    
    headers = {
        "X-Api-Key": api_key,
        "User-Agent": "hummingbot-client",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    async with aiohttp.ClientSession() as session:
        print("=" * 60)
        print("TESTING EXTENDED API AUTHENTICATION")
        print("=" * 60)
        
        # Test 1: Public endpoint (no auth required)
        print("\n1. Testing PUBLIC endpoint (no auth)...")
        try:
            async with session.get(f"{base_url}/api/v1/info/markets") as response:
                print(f"   Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Public endpoint works! Markets count: {len(data)}")
                else:
                    print(f"   ❌ Public endpoint failed")
                    text = await response.text()
                    print(f"   Response: {text[:200]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 2: Account info endpoint (auth required)
        print("\n2. Testing ACCOUNT INFO endpoint (with auth)...")
        try:
            async with session.get(
                f"{base_url}/api/v1/user/account/info",
                headers=headers
            ) as response:
                print(f"   Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Authentication works!")
                    print(f"   Account status: {data.get('data', {}).get('status', 'N/A')}")
                elif response.status == 401:
                    print(f"   ❌ 401 Unauthorized - API key is invalid or not activated")
                    text = await response.text()
                    print(f"   Response: {text[:500]}")
                else:
                    print(f"   ❌ Unexpected status: {response.status}")
                    text = await response.text()
                    print(f"   Response: {text[:500]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 3: Balance endpoint (auth required, 404 if zero)
        print("\n3. Testing BALANCE endpoint (with auth)...")
        try:
            async with session.get(
                f"{base_url}/api/v1/user/balance",
                headers=headers
            ) as response:
                print(f"   Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Balance retrieved!")
                    print(f"   Balance data: {data}")
                elif response.status == 404:
                    print(f"   ℹ️  404 - Normal if balance is zero")
                    print(f"   This means auth worked, but you have no deposits")
                elif response.status == 401:
                    print(f"   ❌ 401 Unauthorized - API key issue")
                    text = await response.text()
                    print(f"   Response: {text[:500]}")
                else:
                    print(f"   Status: {response.status}")
                    text = await response.text()
                    print(f"   Response: {text[:500]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print("\n" + "=" * 60)
        print("DIAGNOSIS:")
        print("=" * 60)
        print("If you got:")
        print("  • 401 on account info -> API key is invalid or not activated")
        print("  • 404 on balance -> Auth works! Just need to deposit USDC")
        print("  • 200 on balance -> Auth works AND you have funds!")
        print("\nTo fix 401 error:")
        print("  1. Check you copied the API key correctly (no spaces)")
        print("  2. Verify API key is from https://app.extended.exchange/api-management")
        print("  3. Ensure account is activated (requires deposit in UI)")
        print("  4. Check API key has 'Trading' permissions enabled")
        print("=" * 60)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python test_extended_auth.py <YOUR_API_KEY>")
        print("\nExample:")
        print("  python test_extended_auth.py abc123def456...")
        sys.exit(1)
    
    api_key = sys.argv[1]
    print(f"\nTesting with API key: {api_key[:10]}...{api_key[-10:]}\n")
    
    asyncio.run(test_extended_api(api_key))

