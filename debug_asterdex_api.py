#!/usr/bin/env python3
"""
Debug script to test AsterDex API endpoints
"""

import urllib.request
import urllib.error
import json

def test_api_endpoint(url, description):
    print(f"\n🧪 Testing: {description}")
    print(f"   URL: {url}")
    
    try:
        # Create a request with basic headers
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.getcode()
            print(f"   Status: {status}")
            
            if status == 200:
                print(f"   ✅ SUCCESS! Endpoint works")
                try:
                    data = json.loads(response.read().decode())
                    print(f"   Response: {json.dumps(data, indent=2)[:300]}...")
                except:
                    print(f"   Response: {response.read().decode()[:300]}...")
            else:
                print(f"   ⚠️  Status {status}")
                
    except urllib.error.HTTPError as e:
        print(f"   HTTP Error {e.code}: {e.reason}")
        if e.code == 404:
            print(f"   ❌ 404 - Endpoint not found")
        elif e.code == 401:
            print(f"   🔐 401 - Authentication required (this is expected for balance endpoint)")
        elif e.code == 403:
            print(f"   🚫 403 - Forbidden (might need authentication)")
    except urllib.error.URLError as e:
        print(f"   ❌ URL Error: {e.reason}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

def main():
    print("🔍 AsterDex API Endpoint Debugger")
    print("=" * 50)
    
    # Test different possible base URLs and endpoints
    base_urls = [
        "https://asterdex.com/api/pro/v1/",
        "https://asterdex.com/api/v1/",
        "https://asterdex.com/api/",
        "https://api.asterdex.com/v1/",
        "https://api.asterdex.com/"
    ]
    
    endpoints = [
        "cash/balance",
        "account/balance",
        "balance",
        "user/balance",
        "wallet/balance",
        "spot/balance"
    ]
    
    print("🎯 Testing different base URLs and endpoints...")
    
    for base_url in base_urls:
        print(f"\n📡 Testing base URL: {base_url}")
        
        # Test a simple endpoint first
        test_api_endpoint(f"{base_url}info", "Info endpoint")
        
        # Test balance endpoints
        for endpoint in endpoints[:2]:  # Test first 2 to avoid too many requests
            test_api_endpoint(f"{base_url}{endpoint}", f"Balance endpoint: {endpoint}")
    
    print(f"\n🎯 Summary:")
    print(f"   - Look for endpoints that return 401 (auth required) - these are likely correct")
    print(f"   - 404 means the endpoint doesn't exist")
    print(f"   - 200 means the endpoint works without auth")
    print(f"   - The correct endpoint should return 401 when called without authentication")

if __name__ == "__main__":
    main()
