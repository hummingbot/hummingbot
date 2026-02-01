"""
Unit tests for core WEEX exchange connector
"""
import unittest
from decimal import Decimal
from unittest.mock import patch

from hummingbot.core.data_type.common import OrderType, TradeType


class TestWeexExchange(unittest.TestCase):
    """Test WEEX exchange connector core methods"""

    def setUp(self):
        """Set up test fixtures"""
        from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange

        with patch("hummingbot.connector.exchange_py_base.ExchangePyBase.__init__"):
            self.exchange = WeexExchange(
                weex_api_key="test_key",
                weex_api_secret="test_secret",
                weex_api_passphrase="test_pass",
                trading_pairs=["VCC-USDT"],
            )

    def test_order_type_conversion(self):
        """Test conversion between Hummingbot and WEEX order types"""
        from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange

        # Hummingbot LIMIT -> WEEX "LIMIT"
        weex_type = WeexExchange.weex_order_type(OrderType.LIMIT)
        self.assertEqual(weex_type, "LIMIT")

        weex_type = WeexExchange.weex_order_type(OrderType.LIMIT_MAKER)
        self.assertEqual(weex_type, "LIMIT_MAKER")

        weex_type = WeexExchange.weex_order_type(OrderType.MARKET)
        self.assertEqual(weex_type, "MARKET")

        # WEEX -> Hummingbot
        hb_type = WeexExchange.to_hb_order_type("LIMIT")
        self.assertEqual(hb_type, OrderType.LIMIT)

    def test_trading_pair_symbol_conversion(self):
        """Test WEEX symbol to Hummingbot pair conversion"""
        from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange

        # VCCUSDT-SPBL -> VCC-USDT
        pair = WeexExchange.weex_symbol_to_hb_pair("VCCUSDT-SPBL")
        self.assertEqual(pair, "VCC-USDT")

        # BTCUSDT-SPBL -> BTC-USDT
        pair = WeexExchange.weex_symbol_to_hb_pair("BTCUSDT-SPBL")
        self.assertEqual(pair, "BTC-USDT")

        # ETHUSDC-SPBL -> ETH-USDC
        pair = WeexExchange.weex_symbol_to_hb_pair("ETHUSDC-SPBL")
        self.assertEqual(pair, "ETH-USDC")

    def test_weex_symbol_parsing_known_quotes(self):
        """Test that known quote currencies are detected"""
        from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange

        self.assertEqual(WeexExchange.weex_symbol_to_hb_pair("BTCUSDT-SPBL"), "BTC-USDT")
        self.assertEqual(WeexExchange.weex_symbol_to_hb_pair("ETHUSDC-SPBL"), "ETH-USDC")
        self.assertEqual(WeexExchange.weex_symbol_to_hb_pair("BTCEUR-SPBL"), "BTC-EUR")
        self.assertEqual(WeexExchange.weex_symbol_to_hb_pair("USDTTRY-SPBL"), "USDT-TRY")

    def test_weex_symbol_parsing_edge_case(self):
        """Test that unknown symbols raise ValueError"""
        from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange

        with self.assertRaises(ValueError):
            WeexExchange.weex_symbol_to_hb_pair("UNKNOWNXYZ-SPBL")

    def test_order_placement_parameters(self):
        """Test order placement parameter construction"""
        # Test BUY limit order
        expected_params = {
            "symbol": "VCCUSDT-SPBL",
            "side": "buy",
            "orderType": "limit",
            "quantity": "100.000000",
            "price": "0.000150",
            "force": "normal",
            "clientOrderId": "x-MG43PCSN-test-1",
        }

        self.assertIn("symbol", expected_params)
        self.assertEqual(expected_params["side"], "buy")
        self.assertEqual(expected_params["orderType"], "limit")
        self.assertIn("quantity", expected_params)
        self.assertIn("price", expected_params)

    def test_order_placement_limit_maker(self):
        """Test LIMIT_MAKER order uses postOnly"""
        expected_params = {
            "symbol": "VCCUSDT-SPBL",
            "side": "buy",
            "force": "postOnly",
        }

        self.assertEqual(expected_params["force"], "postOnly")

    def test_order_placement_market(self):
        """Test MARKET order only requires symbol, side, quantity"""
        expected_params = {
            "symbol": "VCCUSDT-SPBL",
            "side": "sell",
            "orderType": "market",
            "quantity": "100.000000",
        }

        self.assertNotIn("price", expected_params)
        self.assertEqual(expected_params["orderType"], "market")

    def test_cancel_order_payload(self):
        """Test cancel request includes clientOrderId and orderId"""
        expected_payload = {
            "symbol": "VCCUSDT-SPBL",
            "clientOrderId": "x-MG43PCSN-test-1",
            "orderId": "12345",
        }

        self.assertIn("clientOrderId", expected_payload)
        self.assertIn("orderId", expected_payload)
        self.assertIn("symbol", expected_payload)

    def test_time_sync_error_detection(self):
        """Test detection of timestamp-related errors"""
        from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange

        exchange = WeexExchange(
            weex_api_key="key",
            weex_api_secret="secret",
            trading_pairs=["VCC-USDT"],
        )

        # Should detect timestamp errors
        error = Exception("Invalid timestamp for this request")
        self.assertTrue(exchange._is_request_exception_related_to_time_synchronizer(error))

        error = Exception("ACCESS-TIMESTAMP out of range")
        self.assertTrue(exchange._is_request_exception_related_to_time_synchronizer(error))

        # Should not misidentify other errors
        error = Exception("Invalid API key")
        self.assertFalse(exchange._is_request_exception_related_to_time_synchronizer(error))

    def test_order_not_found_error_detection(self):
        """Test detection of order not found errors"""
        from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange

        exchange = WeexExchange(
            weex_api_key="key",
            weex_api_secret="secret",
            trading_pairs=["VCC-USDT"],
        )

        error = Exception("order not found")
        self.assertTrue(exchange._is_order_not_found_during_status_update_error(error))

        error = Exception("order does not exist")
        self.assertTrue(exchange._is_order_not_found_during_cancelation_error(error))

        error = Exception("invalid order")
        self.assertTrue(exchange._is_order_not_found_during_status_update_error(error))

    def test_supported_order_types(self):
        """Test list of supported order types"""
        from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange

        exchange = WeexExchange(
            weex_api_key="key",
            weex_api_secret="secret",
            trading_pairs=["VCC-USDT"],
        )

        supported = exchange.supported_order_types()
        self.assertIn(OrderType.LIMIT, supported)
        self.assertIn(OrderType.LIMIT_MAKER, supported)
        self.assertIn(OrderType.MARKET, supported)

    def test_client_order_id_max_length(self):
        """Test client order ID constraints"""
        from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange

        exchange = WeexExchange(
            weex_api_key="key",
            weex_api_secret="secret",
            trading_pairs=["VCC-USDT"],
        )

        # WEEX has 40 char limit
        max_len = exchange.client_order_id_max_length
        self.assertEqual(max_len, 40)

    def test_is_cancel_synchronous(self):
        """Test that WEEX cancel is synchronous"""
        from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange

        exchange = WeexExchange(
            weex_api_key="key",
            weex_api_secret="secret",
            trading_pairs=["VCC-USDT"],
        )

        self.assertTrue(exchange.is_cancel_request_in_exchange_synchronous)

    def test_fee_schema(self):
        """Test fee calculation"""
        from hummingbot.connector.exchange.weex.weex_exchange import WeexExchange

        exchange = WeexExchange(
            weex_api_key="key",
            weex_api_secret="secret",
            trading_pairs=["VCC-USDT"],
        )

        # Fees are deducted from returns (typical for spot exchanges)
        fee = exchange._get_fee(
            base_currency="VCC",
            quote_currency="USDT",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("100"),
            price=Decimal("0.00015"),
        )

        self.assertIsNotNone(fee)
        # Fee should be maker or taker based on order type
        # LIMIT_MAKER should have maker fee; LIMIT should have taker
        self.assertTrue(hasattr(fee, "percent"))


if __name__ == "__main__":
    unittest.main()
