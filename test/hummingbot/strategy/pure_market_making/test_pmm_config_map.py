import asyncio
import unittest
from collections import Awaitable
from copy import deepcopy

from hummingbot.strategy.pure_market_making.pure_market_making_config_map import (
    pure_market_making_config_map as pmm_config_map,
    on_validate_price_source,
    validate_price_type,
    order_amount_prompt,
    validate_order_amount,
)


class TestPMMConfigMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(pmm_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            pmm_config_map[key] = value

    def test_on_validate_price_source_non_external_market_reset(self):
        pmm_config_map["price_source_exchange"].value = "an_extmkt"
        pmm_config_map["price_source_market"].value = self.trading_pair
        pmm_config_map["take_if_crossed"].value = False

        on_validate_price_source(value="current_market")

        self.assertIsNone(pmm_config_map["price_source_exchange"].value)
        self.assertIsNone(pmm_config_map["price_source_market"].value)
        self.assertIsNone(pmm_config_map["take_if_crossed"].value)

    def test_on_validate_price_source_non_custom_api_reset(self):
        pmm_config_map["price_source_custom_api"].value = "https://someurl.com"

        on_validate_price_source(value="current_market")

        self.assertIsNone(pmm_config_map["price_source_custom_api"].value)

    def test_on_validate_price_source_custom_api_set_price_type(self):
        on_validate_price_source(value="custom_api")

        self.assertEqual(pmm_config_map["price_type"].value, "custom")

    def test_validate_price_type_non_custom_api(self):
        pmm_config_map["price_source"].value = "current_market"

        error = validate_price_type(value="mid_price")
        self.assertIsNone(error)
        error = validate_price_type(value="last_price")
        self.assertIsNone(error)
        error = validate_price_type(value="last_own_trade_price")
        self.assertIsNone(error)
        error = validate_price_type(value="best_bid")
        self.assertIsNone(error)
        error = validate_price_type(value="best_ask")
        self.assertIsNone(error)
        error = validate_price_type(value="inventory_cost")
        self.assertIsNone(error)

        error = validate_price_type(value="custom")
        self.assertIsNotNone(error)

    def test_validate_price_type_custom_api(self):
        pmm_config_map["price_source"].value = "custom_api"

        error = validate_price_type(value="mid_price")
        self.assertIsNotNone(error)
        error = validate_price_type(value="last_price")
        self.assertIsNotNone(error)
        error = validate_price_type(value="last_own_trade_price")
        self.assertIsNotNone(error)
        error = validate_price_type(value="best_bid")
        self.assertIsNotNone(error)
        error = validate_price_type(value="best_ask")
        self.assertIsNotNone(error)
        error = validate_price_type(value="inventory_cost")
        self.assertIsNotNone(error)

        error = validate_price_type(value="custom")
        self.assertIsNone(error)

    def test_order_amount_prompt(self):
        pmm_config_map["market"].value = self.trading_pair
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
