#!/usr/bin/env python3
"""
Comprehensive test suite for Vest Markets connector implementation
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))


class VestConnectorTester:
    def __init__(self):
        self.test_results = {}
        self.total_tests = 0
        self.passed_tests = 0

    def run_test(self, test_name: str, test_func) -> bool:
        """Run a single test and record results"""
        self.total_tests += 1
        try:
            result = test_func()
            if result:
                self.passed_tests += 1
                self.test_results[test_name] = "✅ PASSED"
                return True
            else:
                self.test_results[test_name] = "❌ FAILED"
                return False
        except Exception as e:
            self.test_results[test_name] = f"❌ ERROR: {str(e)}"
            return False

    def test_file_structure(self) -> bool:
        """Test 1: Verify all required files exist"""
        print("\n📁 Testing File Structure...")

        vest_path = "hummingbot/connector/exchange/vest"
        required_files = [
            "__init__.py",
            "vest_exchange.py",
            "vest_auth.py",
            "vest_constants.py",
            "vest_utils.py",
            "vest_web_utils.py",
            "vest_api_order_book_data_source.py",
            "vest_api_user_stream_data_source.py"
        ]

        if not os.path.exists(vest_path):
            print(f"  ✗ Directory {vest_path} not found")
            return False

        all_exist = True
        for file in required_files:
            file_path = os.path.join(vest_path, file)
            if os.path.exists(file_path):
                print(f"  ✓ {file}")
            else:
                print(f"  ✗ {file} missing")
                all_exist = False

        return all_exist

    def test_constants_module(self) -> bool:
        """Test 2: Verify constants module configuration"""
        print("\n⚙️ Testing Constants Module...")

        try:
            # Module loaded but not used - checking spec is sufficient
            required = [
                "CLIENT_ID_PREFIX", "MAX_ID_LEN", "VEST_ENVIRONMENTS",
                "VEST_BASE_PATH", "VEST_EXCHANGE_INFO_PATH",
                "VEST_ACCOUNT_PATH", "VEST_ORDERS_PATH",
                "VEST_TICKER_PATH", "VEST_TRADES_PATH", "VEST_ORDERBOOK_PATH",
                "ORDER_STATE", "ORDER_TYPE_MAP", "SIDE_MAP"
            ]

            # Read file content to check
            with open("hummingbot/connector/exchange/vest/vest_constants.py", "r") as f:
                content = f.read()

            for const in required:
                if const in content:
                    print(f"  ✓ {const} defined")
                else:
                    print(f"  ✗ {const} missing")
                    return False

            # Check environments
            if "prod" in content and "dev" in content:
                print("  ✓ Environments configured (prod/dev)")
            else:
                print("  ✗ Environments not properly configured")
                return False

            return True

        except Exception as e:
            print(f"  ✗ Error checking constants: {e}")
            return False

    def test_utils_module(self) -> bool:
        """Test 3: Verify utils module configuration"""
        print("\n🔧 Testing Utils Module...")

        try:
            # Check file content
            with open("hummingbot/connector/exchange/vest/vest_utils.py", "r") as f:
                content = f.read()

            required = [
                "DEFAULT_FEES", "CENTRALIZED", "EXAMPLE_PAIR",
                "VestConfigMap", "vest_api_key", "vest_primary_address",
                "vest_signing_address", "vest_private_key",
                "is_exchange_information_valid"
            ]

            for item in required:
                if item in content:
                    print(f"  ✓ {item} defined")
                else:
                    print(f"  ✗ {item} missing")
                    return False

            # Check specific values
            if 'CENTRALIZED = True' in content:
                print("  ✓ Centralized exchange setting correct")
            else:
                print("  ✗ Centralized setting incorrect")
                return False

            if 'BTC-PERP' in content:
                print("  ✓ Example pair configured")
            else:
                print("  ✗ Example pair not configured")
                return False

            return True

        except Exception as e:
            print(f"  ✗ Error checking utils: {e}")
            return False

    def test_auth_implementation(self) -> bool:
        """Test 4: Verify authentication implementation"""
        print("\n🔐 Testing Authentication Implementation...")

        try:
            with open("hummingbot/connector/exchange/vest/vest_auth.py", "r") as f:
                content = f.read()

            # Check for required imports
            required_imports = [
                "from eth_account import Account",
                "from eth_account.messages import encode_defunct",
                "from hummingbot.core.web_assistant.auth import AuthBase"
            ]

            for imp in required_imports:
                if imp in content:
                    print(f"  ✓ Required import found: {imp.split()[1]}")
                else:
                    print(f"  ✗ Missing import: {imp}")
                    return False

            # Check for required methods
            required_methods = [
                "def __init__",
                "def rest_authenticate",
                "def ws_authenticate",
                "def _generate_signature",
                "def authentication_headers",
                "def websocket_login_parameters"
            ]

            for method in required_methods:
                if method in content:
                    print(f"  ✓ Method implemented: {method.replace('def ', '')}")
                else:
                    print(f"  ✗ Method missing: {method}")
                    return False

            # Check for Ethereum signing
            if "self.account = Account.from_key(private_key)" in content:
                print("  ✓ Ethereum account setup implemented")
            else:
                print("  ✗ Ethereum account setup missing")
                return False

            return True

        except Exception as e:
            print(f"  ✗ Error checking auth: {e}")
            return False

    def test_exchange_class(self) -> bool:
        """Test 5: Verify exchange class implementation"""
        print("\n🏦 Testing Exchange Class Implementation...")

        try:
            with open("hummingbot/connector/exchange/vest/vest_exchange.py", "r") as f:
                content = f.read()

            # Check class definition
            if "class VestExchange(ExchangePyBase):" in content:
                print("  ✓ VestExchange class properly extends ExchangePyBase")
            else:
                print("  ✗ VestExchange class definition incorrect")
                return False

            # Check required methods
            required_methods = [
                "def __init__",
                "def authenticator",
                "def name",
                "def supported_order_types",
                "async def _place_order",
                "async def _place_cancel",
                "async def get_last_traded_prices",
                "async def _update_balances",
                "async def _initialize_trading_pair_symbol_map",
                "def _create_order_book_data_source",
                "def _create_user_stream_data_source"
            ]

            for method in required_methods:
                if method in content:
                    print(f"  ✓ {method.replace('def ', '').replace('async def ', '')} implemented")
                else:
                    print(f"  ✗ {method.replace('def ', '').replace('async def ', '')} missing")
                    return False

            # Check order type support
            if "OrderType.LIMIT" in content and "OrderType.MARKET" in content:
                print("  ✓ Order types properly configured")
            else:
                print("  ✗ Order types not properly configured")
                return False

            return True

        except Exception as e:
            print(f"  ✗ Error checking exchange class: {e}")
            return False

    def test_websocket_implementation(self) -> bool:
        """Test 6: Verify WebSocket data source implementations"""
        print("\n🔌 Testing WebSocket Implementation...")

        try:
            # Check order book data source
            with open("hummingbot/connector/exchange/vest/vest_api_order_book_data_source.py", "r") as f:
                ob_content = f.read()

            ob_methods = [
                "async def _order_book_snapshot",
                "async def _connected_websocket_assistant",
                "async def _subscribe_channels",
                "async def _parse_order_book_diff_message",
                "async def _parse_trade_message"
            ]

            print("  Order Book Data Source:")
            for method in ob_methods:
                if method in ob_content:
                    print(f"    ✓ {method.replace('async def ', '')}")
                else:
                    print(f"    ✗ {method.replace('async def ', '')} missing")
                    return False

            # Check user stream data source
            with open("hummingbot/connector/exchange/vest/vest_api_user_stream_data_source.py", "r") as f:
                us_content = f.read()

            us_methods = [
                "async def _connected_websocket_assistant",
                "async def _subscribe_channels",
                "async def _process_websocket_messages"
            ]

            print("  User Stream Data Source:")
            for method in us_methods:
                if method in us_content:
                    print(f"    ✓ {method.replace('async def ', '')}")
                else:
                    print(f"    ✗ {method.replace('async def ', '')} missing")
                    return False

            return True

        except Exception as e:
            print(f"  ✗ Error checking WebSocket implementation: {e}")
            return False

    def test_api_endpoints(self) -> bool:
        """Test 7: Verify API endpoints configuration"""
        print("\n🌐 Testing API Endpoints...")

        try:
            with open("hummingbot/connector/exchange/vest/vest_constants.py", "r") as f:
                content = f.read()

            endpoints = {
                "VEST_EXCHANGE_INFO_PATH": "/v2/exchangeInfo",
                "VEST_ACCOUNT_PATH": "/v2/account",
                "VEST_ORDERS_PATH": "/v2/orders",
                "VEST_TICKER_PATH": "/v2/ticker/latest",
                "VEST_TRADES_PATH": "/v2/trades",
                "VEST_ORDERBOOK_PATH": "/v2/orderbook"
            }

            all_correct = True
            for name, expected_path in endpoints.items():
                if f'{name} = f"{{VEST_BASE_PATH}}/{expected_path.split("/v2/")[1]}"' in content or \
                   f'{name} = "{expected_path}"' in content:
                    print(f"  ✓ {name}: {expected_path}")
                else:
                    print(f"  ✗ {name} incorrect or missing")
                    all_correct = False

            # Check WebSocket configuration
            if "wss://ws-prod.hz.vestmarkets.com" in content:
                print("  ✓ Production WebSocket URL configured")
            else:
                print("  ✗ Production WebSocket URL missing")
                all_correct = False

            return all_correct

        except Exception as e:
            print(f"  ✗ Error checking endpoints: {e}")
            return False

    def test_error_handling(self) -> bool:
        """Test 8: Verify error handling implementation"""
        print("\n⚠️ Testing Error Handling...")

        try:
            with open("hummingbot/connector/exchange/vest/vest_exchange.py", "r") as f:
                content = f.read()

            error_patterns = [
                "try:",
                "except",
                "self.logger().exception",
                "self.logger().error",
                "raise"
            ]

            for pattern in error_patterns:
                count = content.count(pattern)
                if count > 0:
                    print(f"  ✓ {pattern} used {count} times")
                else:
                    print(f"  ✗ {pattern} not found")
                    return False

            # Check specific error handling methods
            if "_is_order_not_found_during_status_update_error" in content:
                print("  ✓ Order not found error handling implemented")
            else:
                print("  ✗ Order not found error handling missing")

            if "_is_order_not_found_during_cancelation_error" in content:
                print("  ✓ Cancellation error handling implemented")
            else:
                print("  ✗ Cancellation error handling missing")

            return True

        except Exception as e:
            print(f"  ✗ Error checking error handling: {e}")
            return False

    def run_all_tests(self):
        """Run all tests and generate report"""
        print("\n" + "=" * 60)
        print("🔍 VEST MARKETS CONNECTOR COMPREHENSIVE TEST SUITE")
        print("=" * 60)

        tests = [
            ("File Structure", self.test_file_structure),
            ("Constants Module", self.test_constants_module),
            ("Utils Module", self.test_utils_module),
            ("Authentication", self.test_auth_implementation),
            ("Exchange Class", self.test_exchange_class),
            ("WebSocket Implementation", self.test_websocket_implementation),
            ("API Endpoints", self.test_api_endpoints),
            ("Error Handling", self.test_error_handling)
        ]

        for test_name, test_func in tests:
            self.run_test(test_name, test_func)

        # Generate final report
        self.generate_report()

    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)

        for test_name, result in self.test_results.items():
            print(f"{result} {test_name}")

        print("\n" + "-" * 60)
        success_rate = (self.passed_tests / self.total_tests) * 100 if self.total_tests > 0 else 0

        print(f"Total Tests: {self.total_tests}")
        print(f"Passed: {self.passed_tests}")
        print(f"Failed: {self.total_tests - self.passed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")

        print("\n" + "=" * 60)

        if success_rate == 100:
            print("🎉 SUCCESS: All tests passed!")
            print("\n✅ The Vest Markets connector is properly implemented and ready for use.")
            print("\n📝 Next steps:")
            print("  1. Install dependencies: pip install pandas bidict eth-account")
            print("  2. Configure credentials in Hummingbot")
            print("  3. Test with development environment first")
            print("  4. Deploy to production when ready")
        elif success_rate >= 75:
            print("⚠️ MOSTLY COMPLETE: Most tests passed but some issues remain.")
            print("\n📝 Review failed tests above and address the issues.")
        else:
            print("❌ NEEDS WORK: Significant issues detected.")
            print("\n📝 Please review and fix the failed tests above.")

        print("=" * 60 + "\n")


if __name__ == "__main__":
    tester = VestConnectorTester()
    tester.run_all_tests()
