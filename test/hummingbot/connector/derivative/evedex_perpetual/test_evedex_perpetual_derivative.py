import asyncio
import json
from decimal import Decimal
from typing import Awaitable, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_derivative import EvedexPerpetualDerivative
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType


class EvedexPerpetualDerivativeTests(TestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.domain = "evedex_perpetual"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        
        self.api_key = "0x1234567890abcdef1234567890abcdef12345678"
        self.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"
        
        self.connector = EvedexPerpetualDerivative(
            evedex_perpetual_api_key=self.api_key,
            evedex_perpetual_api_secret=self.api_secret,
            evedex_perpetual_auth_mode="wallet",
            trading_pairs=[self.trading_pair],
            trading_required=True,
            domain=self.domain,
        )
        
        self.connector.logger().setLevel(1)
        self.connector.logger().addHandler(self)

    def tearDown(self) -> None:
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_name(self):
        """Test connector name property."""
        self.assertEqual(self.connector.name, self.domain)

    def test_domain(self):
        """Test domain property."""
        self.assertEqual(self.connector.domain, self.domain)

    def test_trading_pairs(self):
        """Test trading pairs property."""
        self.assertEqual(self.connector.trading_pairs, [self.trading_pair])

    def test_is_trading_required(self):
        """Test trading required property."""
        self.assertTrue(self.connector.is_trading_required)

    def test_is_cancel_request_in_exchange_synchronous(self):
        """Test cancel request is synchronous."""
        self.assertTrue(self.connector.is_cancel_request_in_exchange_synchronous)

    def test_supported_order_types(self):
        """Test supported order types."""
        order_types = self.connector.supported_order_types()
        
        self.assertIn(OrderType.LIMIT, order_types)
        self.assertIn(OrderType.LIMIT_MAKER, order_types)
        self.assertIn(OrderType.MARKET, order_types)

    def test_supported_position_modes(self):
        """Test supported position modes."""
        modes = self.connector.supported_position_modes()
        
        self.assertIn(PositionMode.ONEWAY, modes)
        self.assertIn(PositionMode.HEDGE, modes)

    def test_client_order_id_prefix(self):
        """Test client order ID prefix."""
        self.assertEqual(self.connector.client_order_id_prefix, CONSTANTS.BROKER_ID)

    def test_trading_rules_request_path(self):
        """Test trading rules request path."""
        self.assertEqual(self.connector.trading_rules_request_path, CONSTANTS.EXCHANGE_INFO_URL)

    def test_check_network_request_path(self):
        """Test check network request path."""
        self.assertEqual(self.connector.check_network_request_path, CONSTANTS.PING_URL)

    def test_funding_fee_poll_interval(self):
        """Test funding fee poll interval."""
        self.assertEqual(self.connector.funding_fee_poll_interval, 120)

    def test_quantize_order_price(self):
        """Test order price quantization."""
        price = Decimal("50123.456789")
        quantized = self.connector.quantize_order_price(self.trading_pair, price)
        
        # Should be rounded to 5 significant digits
        self.assertIsInstance(quantized, Decimal)

    def test_authenticator_created_when_trading_required(self):
        """Test authenticator is created when trading is required."""
        self.assertIsNotNone(self.connector.authenticator)

    def test_authenticator_none_when_trading_not_required(self):
        """Test authenticator is None when trading is not required."""
        connector = EvedexPerpetualDerivative(
            evedex_perpetual_api_key=self.api_key,
            evedex_perpetual_api_secret=self.api_secret,
            evedex_perpetual_auth_mode="wallet",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain,
        )
        
        self.assertIsNone(connector.authenticator)

    def test_rate_limits_rules(self):
        """Test rate limits rules are set."""
        limits = self.connector.rate_limits_rules
        self.assertEqual(limits, CONSTANTS.RATE_LIMITS)

    def test_is_order_not_found_during_status_update_error(self):
        """Test order not found error detection during status update."""
        exception = Exception(CONSTANTS.ORDER_NOT_EXIST_MESSAGE)
        self.assertTrue(self.connector._is_order_not_found_during_status_update_error(exception))
        
        other_exception = Exception("Some other error")
        self.assertFalse(self.connector._is_order_not_found_during_status_update_error(other_exception))

    def test_is_order_not_found_during_cancelation_error(self):
        """Test order not found error detection during cancellation."""
        exception = Exception(CONSTANTS.UNKNOWN_ORDER_MESSAGE)
        self.assertTrue(self.connector._is_order_not_found_during_cancelation_error(exception))
        
        other_exception = Exception("Some other error")
        self.assertFalse(self.connector._is_order_not_found_during_cancelation_error(other_exception))

    def test_testnet_domain(self):
        """Test testnet domain configuration."""
        testnet_connector = EvedexPerpetualDerivative(
            evedex_perpetual_api_key=self.api_key,
            evedex_perpetual_api_secret=self.api_secret,
            evedex_perpetual_auth_mode="wallet",
            trading_pairs=[self.trading_pair],
            trading_required=True,
            domain=CONSTANTS.TESTNET_DOMAIN,
        )
        
        self.assertEqual(testnet_connector.domain, CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(testnet_connector.name, CONSTANTS.TESTNET_DOMAIN)

    def test_api_key_auth_mode(self):
        """Test API key authentication mode."""
        api_key_connector = EvedexPerpetualDerivative(
            evedex_perpetual_api_key="test_api_key",
            evedex_perpetual_api_secret="test_api_secret",
            evedex_perpetual_auth_mode="api_key",
            trading_pairs=[self.trading_pair],
            trading_required=True,
            domain=self.domain,
        )
        
        self.assertEqual(api_key_connector._auth_mode, "api_key")


class EvedexPerpetualDerivativeOrderTests(TestCase):
    """Tests for order-related functionality."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.api_key = "0x1234567890abcdef1234567890abcdef12345678"
        self.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"
        
        self.connector = EvedexPerpetualDerivative(
            evedex_perpetual_api_key=self.api_key,
            evedex_perpetual_api_secret=self.api_secret,
            evedex_perpetual_auth_mode="wallet",
            trading_pairs=[self.trading_pair],
            trading_required=True,
            domain="evedex_perpetual",
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_buy_returns_client_order_id(self):
        """Test that buy returns a client order ID."""
        with patch.object(self.connector, "_create_order", new_callable=AsyncMock):
            order_id = self.connector.buy(
                trading_pair=self.trading_pair,
                amount=Decimal("0.1"),
                order_type=OrderType.LIMIT,
                price=Decimal("50000")
            )
            
            self.assertTrue(order_id.startswith("0x"))

    def test_sell_returns_client_order_id(self):
        """Test that sell returns a client order ID."""
        with patch.object(self.connector, "_create_order", new_callable=AsyncMock):
            order_id = self.connector.sell(
                trading_pair=self.trading_pair,
                amount=Decimal("0.1"),
                order_type=OrderType.LIMIT,
                price=Decimal("50000")
            )
            
            self.assertTrue(order_id.startswith("0x"))


class EvedexPerpetualDerivativeBalanceTests(TestCase):
    """Tests for balance-related functionality."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.trading_pair = "BTC-USDT"

    def setUp(self) -> None:
        super().setUp()
        self.api_key = "0x1234567890abcdef1234567890abcdef12345678"
        self.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"
        
        self.connector = EvedexPerpetualDerivative(
            evedex_perpetual_api_key=self.api_key,
            evedex_perpetual_api_secret=self.api_secret,
            evedex_perpetual_auth_mode="wallet",
            trading_pairs=[self.trading_pair],
            trading_required=True,
            domain="evedex_perpetual",
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch.object(EvedexPerpetualDerivative, "_api_get")
    def test_update_balances(self, mock_api_get):
        """Test balance update from API."""
        mock_api_get.return_value = {
            "data": [
                {"asset": "USDT", "total": "10000", "available": "8000"},
                {"asset": "BTC", "total": "1.5", "available": "1.0"}
            ]
        }
        
        self.async_run_with_timeout(self.connector._update_balances())
        
        self.assertEqual(self.connector._account_balances.get("USDT"), Decimal("10000"))
        self.assertEqual(self.connector._account_available_balances.get("USDT"), Decimal("8000"))
        self.assertEqual(self.connector._account_balances.get("BTC"), Decimal("1.5"))
        self.assertEqual(self.connector._account_available_balances.get("BTC"), Decimal("1.0"))
