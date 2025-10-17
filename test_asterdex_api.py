#!/usr/bin/env python3
"""
Test script to check AsterDex API endpoints
"""

import requests
import json

def test_asterdex_endpoints():
    print("🔍 Testing AsterDex API Endpoints")
    print("=" * 50)
    
    base_url = "https://asterdex.com/api/pro/v1/"
    
    # Test different possible endpoints
    endpoints_to_test = [
        "cash/balance",
        "account/balance", 
        "balance",
        "user/balance",
        "wallet/balance",
        "spot/balance",
        "api/balance"
    ]
    
    for endpoint in endpoints_to_test:
        url = f"{base_url}{endpoint}"
        print(f"\n🧪 Testing: {url}")
        
        try:
            # Make a simple GET request (without auth for now)
            response = requests.get(url, timeout=10)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   ✅ SUCCESS! Endpoint works: {endpoint}")
                try:
                    data = response.json()
                    print(f"   Response: {json.dumps(data, indent=2)[:200]}...")
                except:
                    print(f"   Response: {response.text[:200]}...")
            elif response.status_code == 401:
                print(f"   🔐 Authentication required (expected for balance endpoint)")
            elif response.status_code == 404:
                print(f"   ❌ Not found: {endpoint}")
            else:
                print(f"   ⚠️  Status {response.status_code}: {endpoint}")
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n🎯 Summary:")
    print(f"   - Tested {len(endpoints_to_test)} possible endpoints")
    print(f"   - Look for endpoints that return 401 (auth required) or 200 (success)")
    print(f"   - 404 means the endpoint doesn't exist")

if __name__ == "__main__":
    test_asterdex_endpoints()
