import asyncio
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import ArchitectPerpetualDerivative
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType


class TestArchitectPerpetualDerivative(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self):
        self.api_key = "test_api_key"
        self.api_secret = "test_api_secret"
        self.trading_pairs = ["BTC-USD", "ETH-USD"]
        with patch("hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative.ArchitectPerpetualDerivative._create_web_assistants_factory"):
            self.connector = ArchitectPerpetualDerivative(
                architect_perpetual_api_key=self.api_key,
                architect_perpetual_api_secret=self.api_secret,
                trading_pairs=self.trading_pairs,
                trading_required=True,
                domain=CONSTANTS.DOMAIN,
            )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        return self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_name(self):
        self.assertEqual(self.connector.name, CONSTANTS.EXCHANGE_NAME)

    def test_domain(self):
        self.assertEqual(self.connector.domain, CONSTANTS.DOMAIN)

    def test_trading_pairs(self):
        self.assertEqual(self.connector.trading_pairs, self.trading_pairs)

    def test_supported_order_types(self):
        order_types = self.connector.supported_order_types()
        self.assertIn(OrderType.LIMIT, order_types)
        self.assertIn(OrderType.MARKET, order_types)

    def test_supported_position_modes(self):
        modes = self.connector.supported_position_modes()
        self.assertIn(PositionMode.ONEWAY, modes)

    def test_is_cancel_request_in_exchange_synchronous(self):
        self.assertTrue(self.connector.is_cancel_request_in_exchange_synchronous)

    def test_is_trading_required(self):
        self.assertTrue(self.connector.is_trading_required)

    def test_funding_fee_poll_interval(self):
        self.assertEqual(self.connector.funding_fee_poll_interval, 600)

    def test_client_order_id_max_length(self):
        self.assertEqual(self.connector.client_order_id_max_length, CONSTANTS.MAX_ORDER_ID_LEN)

    def test_client_order_id_prefix(self):
        self.assertEqual(self.connector.client_order_id_prefix, CONSTANTS.BROKER_ID)

    def test_get_buy_collateral_token_default(self):
        token = self.connector.get_buy_collateral_token("UNKNOWN-USD")
        self.assertEqual(token, CONSTANTS.DEFAULT_QUOTE_ASSET)

    def test_get_sell_collateral_token_default(self):
        token = self.connector.get_sell_collateral_token("UNKNOWN-USD")
        self.assertEqual(token, CONSTANTS.DEFAULT_QUOTE_ASSET)

    def test_is_request_exception_related_to_time_synchronizer(self):
        error = Exception("timestamp invalid for this request")
        self.assertTrue(self.connector._is_request_exception_related_to_time_synchronizer(error))
        error = Exception("some other error")
        self.assertFalse(self.connector._is_request_exception_related_to_time_synchronizer(error))

    def test_is_order_not_found_during_status_update_error(self):
        error = Exception(CONSTANTS.ORDER_NOT_FOUND_ERROR)
        self.assertTrue(self.connector._is_order_not_found_during_status_update_error(error))

    def test_is_order_not_found_during_cancelation_error(self):
        error = Exception(CONSTANTS.ORDER_NOT_FOUND_ERROR)
        self.assertTrue(self.connector._is_order_not_found_during_cancelation_error(error))


if __name__ == "__main__":
    unittest.main()
