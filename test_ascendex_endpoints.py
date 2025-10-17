#!/usr/bin/env python3
"""
Test script to find the correct AscendEx/AsterDex API endpoints
"""

def test_possible_endpoints():
    print("🔍 Testing Possible AscendEx/AsterDex API Endpoints")
    print("=" * 60)
    
    base_urls = [
        "https://ascendex.com/api/pro/v1/",
        "https://ascendex.com/api/v1/", 
        "https://ascendex.com/api/",
        "https://ascendex.com/",
        "https://api.ascendex.com/v1/",
        "https://api.ascendex.com/"
    ]
    
    balance_endpoints = [
        "cash/balance",
        "account/balance", 
        "balance",
        "user/balance",
        "wallet/balance",
        "spot/balance"
    ]
    
    print("🎯 Possible API structures:")
    print("1. https://ascendex.com/api/pro/v1/cash/balance (current - 404)")
    print("2. https://ascendex.com/api/v1/balance")
    print("3. https://ascendex.com/api/balance") 
    print("4. https://ascendex.com/balance")
    print("5. https://api.ascendex.com/v1/balance")
    print()
    
    print("💡 Quick test with curl:")
    print("   curl -I https://ascendex.com/api/v1/balance")
    print("   curl -I https://ascendex.com/api/balance")
    print("   curl -I https://ascendex.com/balance")
    print()
    
    print("🔧 Next steps:")
    print("1. Test these URLs manually")
    print("2. Look for 401 (auth required) vs 404 (not found)")
    print("3. Update constants with the working endpoint")
    print()
    
    print("📋 URLs to test:")
    for base in base_urls[:3]:  # Test first 3
        for endpoint in balance_endpoints[:2]:  # Test first 2
            print(f"   - {base}{endpoint}")

if __name__ == "__main__":
    test_possible_endpoints()
