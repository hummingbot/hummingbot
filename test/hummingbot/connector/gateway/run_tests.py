#!/usr/bin/env python
"""
Test runner for Gateway connector tests.
Runs all gateway-related tests with proper setup.
"""
import os
import sys
import unittest

# Add hummingbot to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from test.hummingbot.connector.gateway.test_gateway_base import TestGatewayBase  # noqa: E402
from test.hummingbot.connector.gateway.test_gateway_command_simple import TestGatewayCommandSimple  # noqa: E402
from test.hummingbot.connector.gateway.test_gateway_http_client_unit import TestGatewayHttpClientUnit  # noqa: E402
from test.hummingbot.connector.gateway.test_gateway_integration_simple import TestGatewayIntegrationSimple  # noqa: E402
from test.hummingbot.connector.gateway.test_gateway_wallet_mock import TestGatewayWalletMock  # noqa: E402


def run_all_tests():
    """Run all gateway tests"""
    # Create test suite
    suite = unittest.TestSuite()

    # Add test classes
    test_classes = [
        TestGatewayWalletMock,
        TestGatewayBase,
        TestGatewayCommandSimple,
        TestGatewayIntegrationSimple,
        TestGatewayHttpClientUnit,
    ]

    # Add tests from each class
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return 0 if all tests passed, 1 otherwise
    return 0 if result.wasSuccessful() else 1


def run_specific_test(test_name):
    """Run a specific test module"""
    test_mapping = {
        'wallet': TestGatewayWalletMock,
        'base': TestGatewayBase,
        'command': TestGatewayCommandSimple,
        'integration': TestGatewayIntegrationSimple,
        'http_client': TestGatewayHttpClientUnit,
    }

    if test_name not in test_mapping:
        print(f"Unknown test: {test_name}")
        print(f"Available tests: {', '.join(test_mapping.keys())}")
        return 1

    # Create suite for specific test
    suite = unittest.TestLoader().loadTestsFromTestCase(test_mapping[test_name])

    # Run test
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test
        exit_code = run_specific_test(sys.argv[1])
    else:
        # Run all tests
        print("Running all Gateway connector tests...")
        print("=" * 70)
        exit_code = run_all_tests()

    sys.exit(exit_code)
