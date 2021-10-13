import asyncio
import unittest
from collections import Awaitable
from copy import deepcopy

from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making_config_map import (
    cross_exchange_market_making_config_map,
    order_amount_prompt,
    validate_order_amount,
)


class CrossExchangeMarketMakingConfigMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(cross_exchange_market_making_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            cross_exchange_market_making_config_map[key] = value

    def test_order_amount_prompt(self):
        cross_exchange_market_making_config_map["maker_market_trading_pair"].value = self.trading_pair
        prompt = self.async_run_with_timeout(order_amount_prompt())
        expected = f"What is the amount of {self.base_asset} per order? >>> "

        self.assertEqual(expected, prompt)

    def test_validate_order_amount_success(self):
        ret = self.async_run_with_timeout(validate_order_amount("1"))

        self.assertIsNone(ret)

    def test_validate_order_amount_invalid_value(self):
        ret = self.async_run_with_timeout(validate_order_amount("0"))
        expected = "Order amount must be a positive value."

        self.assertEqual(expected, ret)

    def test_validate_order_amount_invalid_input(self):
        ret = self.async_run_with_timeout(validate_order_amount("No"))
        expected = "Invalid order amount."

        self.assertEqual(expected, ret)
