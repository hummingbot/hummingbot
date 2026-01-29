"""
Standalone tests for Architect Perpetual connector
These tests verify the connector code without full Hummingbot dependencies
"""
import unittest
import ast
import os


class TestConnectorSyntax(unittest.TestCase):
    """Test that all connector files have valid Python syntax"""

    CONNECTOR_PATH = "hummingbot/connector/derivative/architect_perpetual"

    def _check_syntax(self, filename):
        filepath = os.path.join(self.CONNECTOR_PATH, filename)
        with open(filepath, 'r') as f:
            source = f.read()
        try:
            ast.parse(source)
            return True
        except SyntaxError as e:
            self.fail(f"Syntax error in {filename}: {e}")

    def test_constants_syntax(self):
        self._check_syntax("architect_perpetual_constants.py")

    def test_auth_syntax(self):
        self._check_syntax("architect_perpetual_auth.py")

    def test_utils_syntax(self):
        self._check_syntax("architect_perpetual_utils.py")

    def test_web_utils_syntax(self):
        self._check_syntax("architect_perpetual_web_utils.py")

    def test_derivative_syntax(self):
        self._check_syntax("architect_perpetual_derivative.py")

    def test_order_book_data_source_syntax(self):
        self._check_syntax("architect_perpetual_api_order_book_data_source.py")

    def test_user_stream_data_source_syntax(self):
        self._check_syntax("architect_perpetual_user_stream_data_source.py")


class TestConnectorStructure(unittest.TestCase):
    """Test that connector files contain required elements"""

    CONNECTOR_PATH = "hummingbot/connector/derivative/architect_perpetual"

    def _read_file(self, filename):
        filepath = os.path.join(self.CONNECTOR_PATH, filename)
        with open(filepath, 'r') as f:
            return f.read()

    def test_constants_has_exchange_name(self):
        content = self._read_file("architect_perpetual_constants.py")
        self.assertIn("EXCHANGE_NAME", content)
        self.assertIn("architect_perpetual", content)

    def test_constants_has_endpoints(self):
        content = self._read_file("architect_perpetual_constants.py")
        self.assertIn("PERPETUAL_ENDPOINT", content)
        self.assertIn("TESTNET_ENDPOINT", content)
        self.assertIn("app.architect.co", content)

    def test_constants_has_rate_limits(self):
        content = self._read_file("architect_perpetual_constants.py")
        self.assertIn("RATE_LIMITS", content)
        self.assertIn("RateLimit", content)

    def test_constants_has_order_states(self):
        content = self._read_file("architect_perpetual_constants.py")
        self.assertIn("ORDER_STATE", content)
        self.assertIn("OrderState", content)

    def test_auth_has_class(self):
        content = self._read_file("architect_perpetual_auth.py")
        self.assertIn("class ArchitectPerpetualAuth", content)
        self.assertIn("api_key", content)
        self.assertIn("api_secret", content)

    def test_auth_has_async_methods(self):
        content = self._read_file("architect_perpetual_auth.py")
        self.assertIn("async def rest_authenticate", content)
        self.assertIn("async def ws_authenticate", content)
        self.assertIn("async def get_architect_client", content)

    def test_derivative_has_class(self):
        content = self._read_file("architect_perpetual_derivative.py")
        self.assertIn("class ArchitectPerpetualDerivative", content)
        self.assertIn("PerpetualDerivativePyBase", content)

    def test_derivative_has_order_methods(self):
        content = self._read_file("architect_perpetual_derivative.py")
        self.assertIn("def buy(", content)
        self.assertIn("def sell(", content)
        self.assertIn("async def _place_cancel", content)
        self.assertIn("async def _create_order", content)

    def test_derivative_has_update_methods(self):
        content = self._read_file("architect_perpetual_derivative.py")
        self.assertIn("async def _update_balances", content)
        self.assertIn("async def _update_positions", content)
        self.assertIn("async def _update_orders", content)

    def test_order_book_has_class(self):
        content = self._read_file("architect_perpetual_api_order_book_data_source.py")
        self.assertIn("class ArchitectPerpetualAPIOrderBookDataSource", content)
        self.assertIn("PerpetualAPIOrderBookDataSource", content)

    def test_order_book_has_snapshot_methods(self):
        content = self._read_file("architect_perpetual_api_order_book_data_source.py")
        self.assertIn("async def _request_order_book_snapshot", content)
        self.assertIn("async def _order_book_snapshot", content)

    def test_order_book_has_streaming(self):
        content = self._read_file("architect_perpetual_api_order_book_data_source.py")
        self.assertIn("async def listen_for_subscriptions", content)
        self.assertIn("stream_l2_book_updates", content)

    def test_user_stream_has_class(self):
        content = self._read_file("architect_perpetual_user_stream_data_source.py")
        self.assertIn("class ArchitectPerpetualUserStreamDataSource", content)
        self.assertIn("UserStreamTrackerDataSource", content)

    def test_user_stream_has_listener(self):
        content = self._read_file("architect_perpetual_user_stream_data_source.py")
        self.assertIn("async def listen_for_user_stream", content)
        self.assertIn("stream_orderflow", content)


class TestArchitectSDKIntegration(unittest.TestCase):
    """Test that connector properly integrates with Architect SDK"""

    CONNECTOR_PATH = "hummingbot/connector/derivative/architect_perpetual"

    def _read_file(self, filename):
        filepath = os.path.join(self.CONNECTOR_PATH, filename)
        with open(filepath, 'r') as f:
            return f.read()

    def test_uses_architect_sdk_connect(self):
        content = self._read_file("architect_perpetual_auth.py")
        self.assertIn("from architect_py import AsyncClient", content)
        self.assertIn("AsyncClient.connect", content)

    def test_derivative_imports_architect_sdk(self):
        content = self._read_file("architect_perpetual_derivative.py")
        self.assertIn("from architect_py import", content)

    def test_uses_architect_order_types(self):
        content = self._read_file("architect_perpetual_derivative.py")
        self.assertIn("OrderDir", content)
        self.assertIn("TimeInForce", content)

    def test_order_book_uses_l2_snapshot(self):
        content = self._read_file("architect_perpetual_api_order_book_data_source.py")
        self.assertIn("get_l2_book_snapshot", content)

    def test_user_stream_uses_orderflow(self):
        content = self._read_file("architect_perpetual_user_stream_data_source.py")
        self.assertIn("stream_orderflow", content)


class TestConfigMap(unittest.TestCase):
    """Test the configuration map structure"""

    CONNECTOR_PATH = "hummingbot/connector/derivative/architect_perpetual"

    def _read_file(self, filename):
        filepath = os.path.join(self.CONNECTOR_PATH, filename)
        with open(filepath, 'r') as f:
            return f.read()

    def test_config_has_api_key_field(self):
        content = self._read_file("architect_perpetual_utils.py")
        self.assertIn("architect_perpetual_api_key", content)

    def test_config_has_api_secret_field(self):
        content = self._read_file("architect_perpetual_utils.py")
        self.assertIn("architect_perpetual_api_secret", content)

    def test_config_has_paper_trading_field(self):
        content = self._read_file("architect_perpetual_utils.py")
        self.assertIn("architect_perpetual_paper_trading", content)

    def test_config_has_secure_fields(self):
        content = self._read_file("architect_perpetual_utils.py")
        self.assertIn("is_secure=True", content)

    def test_config_has_default_fees(self):
        content = self._read_file("architect_perpetual_utils.py")
        self.assertIn("DEFAULT_FEES", content)
        self.assertIn("TradeFeeSchema", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
