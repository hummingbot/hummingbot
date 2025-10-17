#!/usr/bin/env python3
"""
Test script to compare AscendEx vs AsterDex API endpoints
"""

def test_domains():
    print("🔍 Testing AscendEx vs AsterDex API Domains")
    print("=" * 60)
    
    domains_to_test = [
        "https://ascendex.com/api/pro/v1/cash/balance",
        "https://asterdex.com/api/pro/v1/cash/balance", 
        "https://ascendex.com/api/pro/v1/info",
        "https://asterdex.com/api/pro/v1/info"
    ]
    
    print("🎯 Possible scenarios:")
    print("1. AsterDex is a rebranded AscendEx - should use ascendex.com")
    print("2. AsterDex is a separate exchange - should use asterdex.com with different endpoints")
    print("3. AsterDex uses the same API as AscendEx but different domain")
    print()
    
    print("📋 URLs to test:")
    for url in domains_to_test:
        print(f"   - {url}")
    
    print()
    print("🔧 Next steps:")
    print("1. Test these URLs manually in a browser or with curl")
    print("2. Check which domain returns 401 (auth required) vs 404 (not found)")
    print("3. Update the constants file with the correct domain and endpoints")
    
    print()
    print("💡 Quick test with curl:")
    print("   curl -I https://ascendex.com/api/pro/v1/info")
    print("   curl -I https://asterdex.com/api/pro/v1/info")

if __name__ == "__main__":
    test_domains()
