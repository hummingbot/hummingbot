import unittest
from copy import deepcopy

from hummingbot.strategy.perpetual_market_making.perpetual_market_making_config_map import (
    perpetual_market_making_config_map as perpetual_mm_config_map,
    on_validate_price_source,
    validate_price_type,
    order_amount_prompt,
)


class TestPMMConfigMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(perpetual_mm_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            perpetual_mm_config_map[key] = value

    def test_on_validate_price_source_non_external_market_reset(self):
        perpetual_mm_config_map["price_source_derivative"].value = "an_extmkt"
        perpetual_mm_config_map["price_source_market"].value = self.trading_pair
        perpetual_mm_config_map["take_if_crossed"].value = False

        on_validate_price_source(value="current_market")

        self.assertIsNone(perpetual_mm_config_map["price_source_derivative"].value)
        self.assertIsNone(perpetual_mm_config_map["price_source_market"].value)
        self.assertIsNone(perpetual_mm_config_map["take_if_crossed"].value)

    def test_on_validate_price_source_non_custom_api_reset(self):
        perpetual_mm_config_map["price_source_custom_api"].value = "https://someurl.com"

        on_validate_price_source(value="current_market")

        self.assertIsNone(perpetual_mm_config_map["price_source_custom_api"].value)

    def test_on_validate_price_source_custom_api_set_price_type(self):
        on_validate_price_source(value="custom_api")

        self.assertEqual(perpetual_mm_config_map["price_type"].value, "custom")

    def test_validate_price_type_non_custom_api(self):
        perpetual_mm_config_map["price_source"].value = "current_market"

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

        error = validate_price_type(value="custom")
        self.assertIsNotNone(error)

    def test_validate_price_type_custom_api(self):
        perpetual_mm_config_map["price_source"].value = "custom_api"

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

        error = validate_price_type(value="custom")
        self.assertIsNone(error)

    def test_order_amount_prompt(self):
        perpetual_mm_config_map["market"].value = self.trading_pair
        prompt = order_amount_prompt()
        expected = f"What is the amount of {self.base_asset} per order? >>> "

        self.assertEqual(expected, prompt)
