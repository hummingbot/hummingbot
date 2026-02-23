import asyncio
from decimal import Decimal
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import GRVTPerpetualDerivative
from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState

class TestGRVTPerpetualDerivative(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "test_api_key"
        self.api_secret = "0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318"
        self.sub_account_id = "12345"
        
        self.exchange = GRVTPerpetualDerivative(
            client_config_map=AsyncMock(),
            grvt_perpetual_api_key=self.api_key,
            grvt_perpetual_api_secret=self.api_secret,
            grvt_perpetual_sub_account_id=self.sub_account_id,
            trading_pairs=["BTC-USDT"],
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_supported_order_types(self):
        supported_types = self.exchange.supported_order_types()
        self.assertIn(OrderType.LIMIT, supported_types)
        self.assertIn(OrderType.MARKET, supported_types)

    def test_supported_position_modes(self):
        supported_modes = self.exchange.supported_position_modes()
        self.assertEqual(1, len(supported_modes))
        self.assertIn(PositionMode.ONEWAY, supported_modes)

    def test_client_order_id_prefix(self):
        self.assertEqual("HBOT", self.exchange.client_order_id_prefix)
