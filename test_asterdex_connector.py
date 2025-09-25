#!/usr/bin/env python3
"""
Simple test script to verify AsterDex connector functionality
"""

import sys
import os

# Add the hummingbot directory to Python path
sys.path.insert(0, '/Users/massloreti/hummingbot')

def test_asterdex_imports():
    """Test if we can import the AsterDex connector modules"""
    try:
        print("🧪 Testing AsterDex connector imports...")
        
        # Test basic imports
        from hummingbot.connector.exchange.asterdex import asterdex_constants
        print("✅ asterdex_constants imported successfully")
        
        from hummingbot.connector.exchange.asterdex import asterdex_utils
        print("✅ asterdex_utils imported successfully")
        
        from hummingbot.connector.exchange.asterdex import asterdex_auth
        print("✅ asterdex_auth imported successfully")
        
        from hummingbot.connector.exchange.asterdex import asterdex_web_utils
        print("✅ asterdex_web_utils imported successfully")
        
        from hummingbot.connector.exchange.asterdex.asterdex_exchange import AsterdexExchange
        print("✅ AsterdexExchange class imported successfully")
        
        from hummingbot.connector.exchange.asterdex.asterdex_api_order_book_data_source import AsterdexAPIOrderBookDataSource
        print("✅ AsterdexAPIOrderBookDataSource imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_asterdex_configuration():
    """Test AsterDex configuration"""
    try:
        print("\n🔧 Testing AsterDex configuration...")
        
        from hummingbot.connector.exchange.asterdex import asterdex_constants as CONSTANTS
        from hummingbot.connector.exchange.asterdex import asterdex_utils as utils
        
        # Test constants
        print(f"✅ Exchange name: {CONSTANTS.EXCHANGE_NAME}")
        print(f"✅ Public REST URL: {CONSTANTS.PUBLIC_REST_URL}")
        print(f"✅ WebSocket URL: {CONSTANTS.WS_URL}")
        
        # Test config map
        config_map = utils.AsterdexConfigMap()
        print(f"✅ Connector name: {config_map.connector}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def test_asterdex_rate_source():
    """Test AsterDex rate source"""
    try:
        print("\n📊 Testing AsterDex rate source...")
        
        from hummingbot.core.rate_oracle.sources.asterdex_rate_source import AsterdexRateSource
        
        rate_source = AsterdexRateSource()
        print(f"✅ Rate source name: {rate_source.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Rate source error: {e}")
        return False

def test_asterdex_in_client_config():
    """Test if AsterDex is registered in client config"""
    try:
        print("\n⚙️ Testing AsterDex in client configuration...")
        
        from hummingbot.client.config.client_config_map import RATE_SOURCE_MODES
        
        if 'asterdex' in RATE_SOURCE_MODES:
            print("✅ AsterDex found in RATE_SOURCE_MODES")
        else:
            print("❌ AsterDex not found in RATE_SOURCE_MODES")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Client config error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 AsterDex Connector Test Suite")
    print("=" * 50)
    
    tests = [
        test_asterdex_imports,
        test_asterdex_configuration,
        test_asterdex_rate_source,
        test_asterdex_in_client_config
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! AsterDex connector is ready!")
        print("\n📝 Next steps:")
        print("1. Get your AsterDex API credentials")
        print("2. Set up the full HummingBot environment when ready")
        print("3. Use 'connect asterdex' in HummingBot to test with real API")
    else:
        print("⚠️ Some tests failed. Check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
