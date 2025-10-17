#!/usr/bin/env python3
"""
Test script to verify AsterDex API key format and authentication
"""

import asyncio
import aiohttp
import time
import hashlib
import hmac

async def test_api_key_format():
    print("🔍 Testing AsterDex API Key Format")
    print("=" * 50)
    
    # Test different possible API key formats
    test_keys = [
        "test_key_123456789",  # Simple format
        "test-key-123456789",  # With dashes
        "test.key.123456789",  # With dots
        "test_key_12345678901234567890",  # Longer format
        "12345678901234567890",  # Numeric only
    ]
    
    base_url = "https://asterdex.com/api/v1/"
    endpoint = "balance"
    
    for i, api_key in enumerate(test_keys):
        print(f"\n🧪 Test {i+1}: Testing API key format: {api_key[:10]}...")
        
        # Generate auth headers (same as AsterDex connector)
        secret_key = "test_secret_key"  # Dummy secret for testing
        timestamp = str(int(time.time() * 1000))
        message = timestamp + endpoint
        signature = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
        
        headers = {
            "x-auth-key": api_key,
            "x-auth-signature": signature,
            "x-auth-timestamp": timestamp,
            "Content-Type": "application/json"
        }
        
        url = f"{base_url}{endpoint}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    status = response.status
                    text = await response.text()
                    
                    if status == 401:
                        if "API-key format invalid" in text:
                            print(f"   ❌ Format invalid: {api_key[:10]}...")
                        elif "Invalid signature" in text:
                            print(f"   ✅ Format OK, signature issue: {api_key[:10]}...")
                        else:
                            print(f"   ⚠️  Other 401 error: {api_key[:10]}... - {text[:100]}")
                    elif status == 403:
                        print(f"   ✅ Format OK, permission issue: {api_key[:10]}...")
                    else:
                        print(f"   ⚠️  Unexpected status {status}: {api_key[:10]}...")
                        
        except Exception as e:
            print(f"   ❌ Error testing {api_key[:10]}...: {e}")
    
    print("\n💡 What this tells us:")
    print("   - If all show 'format invalid': AsterDex uses different auth format")
    print("   - If some show 'signature issue': Format is OK, need real credentials")
    print("   - If some show 'permission issue': Format is OK, need valid API key")

if __name__ == "__main__":
    asyncio.run(test_api_key_format())
