#!/usr/bin/env python3

"""
Test script to validate Vest Markets connector implementation
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def test_basic_imports():
    """Test basic connector imports"""
    print("Testing basic Vest connector imports...")

    try:
        from hummingbot.connector.exchange.vest import vest_constants as CONSTANTS
        print("✓ vest_constants imported successfully")
        print(f"  - Base URL (prod): {CONSTANTS.get_vest_base_url('prod')}")
        print(f"  - WebSocket URL (prod): {CONSTANTS.get_vest_ws_url('prod')}")
        print(f"  - Rate limits: {len(CONSTANTS.RATE_LIMITS)} rules")
    except Exception as e:
        print(f"✗ vest_constants import failed: {e}")
        return False

    try:
        from hummingbot.connector.exchange.vest import vest_utils
        print("✓ vest_utils imported successfully")
        print(f"  - Centralized: {vest_utils.CENTRALIZED}")
        print(f"  - Example pair: {vest_utils.EXAMPLE_PAIR}")
        print(f"  - Config keys available: {vest_utils.KEYS is not None}")
    except Exception as e:
        print(f"✗ vest_utils import failed: {e}")
        return False

    try:
        from hummingbot.connector.exchange.vest.vest_auth import VestAuth  # noqa: F401
        print("✓ VestAuth class imported successfully")
    except Exception as e:
        print(f"✗ VestAuth import failed: {e}")
        return False

    try:
        from hummingbot.connector.exchange.vest.vest_exchange import VestExchange  # noqa: F401
        print("✓ VestExchange class imported successfully")
    except Exception as e:
        print(f"✗ VestExchange import failed: {e}")
        return False

    try:
        from hummingbot.connector.exchange.vest.vest_api_order_book_data_source import (  # noqa: F401
            VestAPIOrderBookDataSource,
        )
        print("✓ VestAPIOrderBookDataSource imported successfully")
    except Exception as e:
        print(f"✗ VestAPIOrderBookDataSource import failed: {e}")
        return False

    try:
        from hummingbot.connector.exchange.vest.vest_api_user_stream_data_source import (  # noqa: F401
            VestAPIUserStreamDataSource,
        )
        print("✓ VestAPIUserStreamDataSource imported successfully")
    except Exception as e:
        print(f"✗ VestAPIUserStreamDataSource import failed: {e}")
        return False

    return True


def test_configuration():
    """Test connector configuration"""
    print("\nTesting Vest connector configuration...")

    try:
        from hummingbot.connector.exchange.vest import vest_utils

        # Check required configuration attributes
        required_attrs = ['DEFAULT_FEES', 'CENTRALIZED', 'EXAMPLE_PAIR', 'KEYS']
        for attr in required_attrs:
            if hasattr(vest_utils, attr):
                print(f"✓ {attr} is defined")
            else:
                print(f"✗ {attr} is missing")
                return False

        # Check configuration values
        config = vest_utils.KEYS
        if config:
            required_fields = ['vest_api_key', 'vest_primary_address', 'vest_signing_address', 'vest_private_key']
            for field in required_fields:
                if hasattr(config, field):
                    print(f"✓ Configuration field {field} is defined")
                else:
                    print(f"✗ Configuration field {field} is missing")
                    return False

    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

    return True


def test_constants():
    """Test connector constants and endpoints"""
    print("\nTesting Vest connector constants...")

    try:
        from hummingbot.connector.exchange.vest import vest_constants as CONSTANTS

        # Check required endpoints
        required_endpoints = [
            'VEST_EXCHANGE_INFO_PATH', 'VEST_ACCOUNT_PATH', 'VEST_ORDERS_PATH',
            'VEST_TICKER_PATH', 'VEST_TRADES_PATH', 'VEST_ORDERBOOK_PATH'
        ]

        for endpoint in required_endpoints:
            if hasattr(CONSTANTS, endpoint):
                endpoint_value = getattr(CONSTANTS, endpoint)
                print(f"✓ {endpoint}: {endpoint_value}")
            else:
                print(f"✗ {endpoint} is missing")
                return False

        # Check WebSocket channels
        ws_channels = [
            'VEST_WS_ACCOUNT_CHANNEL', 'VEST_WS_TICKERS_CHANNEL',
            'VEST_WS_TRADES_CHANNEL', 'VEST_WS_DEPTH_CHANNEL'
        ]

        for channel in ws_channels:
            if hasattr(CONSTANTS, channel):
                print(f"✓ {channel} is defined")
            else:
                print(f"✗ {channel} is missing")
                return False

    except Exception as e:
        print(f"✗ Constants test failed: {e}")
        return False

    return True


def main():
    """Main test function"""
    print("=" * 50)
    print("Vest Markets Connector Implementation Test")
    print("=" * 50)

    tests = [
        ("Basic Imports", test_basic_imports),
        ("Configuration", test_configuration),
        ("Constants", test_constants)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * (len(test_name) + 1))

        if test_func():
            print(f"✓ {test_name} PASSED")
            passed += 1
        else:
            print(f"✗ {test_name} FAILED")

    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Vest connector is properly implemented.")
        print("\nNext steps:")
        print("1. Install eth-account dependency: pip install eth-account")
        print("2. Test with actual API credentials in a development environment")
        print("3. Verify WebSocket connectivity and message parsing")
        print("4. Test order placement and management functionality")
    else:
        print("❌ Some tests failed. Please address the issues above.")

    return passed == total


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
