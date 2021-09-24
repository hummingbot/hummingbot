import asyncio
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import patch, AsyncMock

from hummingbot.client.config.config_helpers import minimum_order_amount
from hummingbot.client.config.global_config_map import global_config_map


class ConfigHelpersTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def get_async_sleep_fn(delay: float):
        async def async_sleep(*_, **__):
            await asyncio.sleep(delay)
        return async_sleep

    def test_minimum_order_amount_no_default_min_quote(self):
        global_config_map["min_quote_order_amount"].value = {"USDT": Decimal("10")}
        min_amount = self.async_run_with_timeout(
            minimum_order_amount(exchange="binance", trading_pair="BTC-USDC")
        )

        self.assertEqual(0, min_amount)

    @patch("hummingbot.client.config.config_helpers.get_last_price")
    def test_minimum_order_amount_with_default_min_quote_and_last_price(
        self, get_last_price_mock: AsyncMock
    ):
        get_last_price_mock.return_value = Decimal("5")
        global_config_map["create_command_timeout"].value = 10
        global_config_map["min_quote_order_amount"].value = {"USDT": Decimal("10")}
        min_amount = self.async_run_with_timeout(
            minimum_order_amount(exchange="binance", trading_pair="BTC-USDT")
        )

        self.assertEqual(2, min_amount)

    @patch("hummingbot.client.config.config_helpers.get_last_price")
    def test_minimum_order_amount_with_default_min_quote_and_fail_to_get_last_price(
        self, get_last_price_mock: AsyncMock
    ):
        get_last_price_mock.side_effect = self.get_async_sleep_fn(delay=0.02)
        global_config_map["create_command_timeout"].value = 0.01
        global_config_map["min_quote_order_amount"].value = {"USDT": Decimal("10")}
        min_amount = self.async_run_with_timeout(
            minimum_order_amount(exchange="binance", trading_pair="BTC-USDT")
        )

        self.assertEqual(0, min_amount)
