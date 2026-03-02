import asyncio
from decimal import Decimal
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import (
    ArchitectPerpetualDerivative,
)
from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType


class ArchitectPerpetualDerivativeTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "test_api_key"
        self.api_secret = "test_api_secret"
        self.trading_pairs = ["BTC-USD", "ETH-USD"]

        self.connector = ArchitectPerpetualDerivative(
            architect_perpetual_api_key=self.api_key,
            architect_perpetual_api_secret=self.api_secret,
            trading_pairs=self.trading_pairs,
            trading_required=True,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_name(self):
        self.assertEqual(self.connector.name, CONSTANTS.DOMAIN)

    def test_domain(self):
        self.assertEqual(self.connector.domain, CONSTANTS.DOMAIN)

    def test_trading_pairs(self):
        self.assertEqual(self.connector.trading_pairs, self.trading_pairs)

    def test_is_trading_required(self):
        self.assertTrue(self.connector.is_trading_required)

    def test_is_trading_required_false(self):
        connector = ArchitectPerpetualDerivative(
            architect_perpetual_api_key=self.api_key,
            architect_perpetual_api_secret=self.api_secret,
            trading_pairs=self.trading_pairs,
            trading_required=False,
        )
        self.assertFalse(connector.is_trading_required)

    def test_client_order_id_max_length(self):
        self.assertEqual(self.connector.client_order_id_max_length, CONSTANTS.MAX_ORDER_ID_LEN)

    def test_client_order_id_prefix(self):
        self.assertEqual(self.connector.client_order_id_prefix, CONSTANTS.BROKER_ID)

    def test_supported_order_types(self):
        order_types = self.connector.supported_order_types()
        self.assertIn(OrderType.LIMIT, order_types)
        self.assertIn(OrderType.MARKET, order_types)

    def test_supported_position_modes(self):
        position_modes = self.connector.supported_position_modes()
        self.assertIn(PositionMode.ONEWAY, position_modes)

    def test_is_cancel_request_in_exchange_synchronous(self):
        self.assertTrue(self.connector.is_cancel_request_in_exchange_synchronous)

    def test_funding_fee_poll_interval(self):
        self.assertEqual(self.connector.funding_fee_poll_interval, 120)

    def test_trading_rules_request_path(self):
        self.assertEqual(self.connector.trading_rules_request_path, CONSTANTS.INSTRUMENTS_URL)

    def test_trading_pairs_request_path(self):
        self.assertEqual(self.connector.trading_pairs_request_path, CONSTANTS.INSTRUMENTS_URL)

    def test_check_network_request_path(self):
        self.assertEqual(self.connector.check_network_request_path, CONSTANTS.TICKERS_URL)

    def test_exchange_symbol_to_trading_pair(self):
        result = self.connector.exchange_symbol_to_trading_pair("BTC-USD-PERP")
        self.assertEqual(result, "BTC-USD")

    def test_exchange_symbol_to_trading_pair_underscore(self):
        result = self.connector.exchange_symbol_to_trading_pair("ETH_USD")
        self.assertEqual(result, "ETH-USD")

    def test_trading_pair_to_exchange_symbol(self):
        result = self.connector.trading_pair_to_exchange_symbol("BTC-USD")
        self.assertEqual(result, "BTC-USD-PERP")

    def test_trading_pair_to_exchange_symbol_eth(self):
        result = self.connector.trading_pair_to_exchange_symbol("ETH-USD")
        self.assertEqual(result, "ETH-USD-PERP")

    def test_symbol_conversion_roundtrip(self):
        original = "SOL-USD"
        exchange = self.connector.trading_pair_to_exchange_symbol(original)
        back = self.connector.exchange_symbol_to_trading_pair(exchange)
        self.assertEqual(back, original)

    def test_authenticator_with_trading_required(self):
        auth = self.connector.authenticator
        self.assertIsNotNone(auth)

    def test_authenticator_without_trading_required(self):
        connector = ArchitectPerpetualDerivative(
            architect_perpetual_api_key=self.api_key,
            architect_perpetual_api_secret=self.api_secret,
            trading_pairs=self.trading_pairs,
            trading_required=False,
        )
        auth = connector.authenticator
        self.assertIsNone(auth)

    def test_rate_limits_rules(self):
        limits = self.connector.rate_limits_rules
        self.assertEqual(limits, CONSTANTS.RATE_LIMITS)
        self.assertTrue(len(limits) > 0)

    def test_is_request_exception_related_to_time_synchronizer(self):
        result = self.connector._is_request_exception_related_to_time_synchronizer(Exception("test"))
        self.assertFalse(result)
