import unittest

from copy import deepcopy

from hummingbot.strategy.triangular_arbitrage.triangular_arbitrage_config_map import (
    triangular_arbitrage_config_map,
    target_currency_prompt,
    first_auxilliary_prompt,
    second_auxilliary_prompt,
    replacement_source_left_prompt,
    replacement_source_bottom_prompt,
    replacement_source_right_prompt,
    replacement_target_left_prompt,
    replacement_target_bottom_prompt,
    replacement_target_right_prompt,
)


class TriangularArbitrageConfigMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.primary_exchange = "binance"
        cls.target_currency = "ETH"
        cls.first_aux_currency = "BTC"
        cls.second_aux_currency = "USDT"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(triangular_arbitrage_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            triangular_arbitrage_config_map[key] = value

    def test_target_currency_prompt(self):
        triangular_arbitrage_config_map["exchange"].value = self.primary_exchange
        prompt = target_currency_prompt()
        expected = f"Enter the name of the currency you would like to accrue on {self.primary_exchange} >>> "

        self.assertEqual(expected, prompt)

    def test_first_auxilliary_prompt(self):
        triangular_arbitrage_config_map["exchange"].value = self.primary_exchange
        prompt = first_auxilliary_prompt()
        expected = f"Enter the name of the first auxilliary currency to use on {self.primary_exchange} >>> "

        self.assertEqual(expected, prompt)

    def test_second_auxilliary_prompt(self):
        triangular_arbitrage_config_map["exchange"].value = self.primary_exchange
        prompt = second_auxilliary_prompt()
        expected = f"Enter the name of the second auxilliary currency to use on {self.primary_exchange} >>> "

        self.assertEqual(expected, prompt)

    def test_replacement_source_left_prompt(self):
        triangular_arbitrage_config_map["target_currency"].value = self.target_currency
        triangular_arbitrage_config_map["first_aux_currency"].value = self.first_aux_currency

        prompt = replacement_source_left_prompt()
        expected = f"Enter the name of the currency which will be used for {self.target_currency} on the edge which connects {self.target_currency} to {self.first_aux_currency} >>> "

        self.assertEqual(expected, prompt)

    def test_replacement_target_left_prompt(self):
        triangular_arbitrage_config_map["target_currency"].value = self.target_currency
        triangular_arbitrage_config_map["first_aux_currency"].value = self.first_aux_currency

        prompt = replacement_target_left_prompt()
        expected = f"Enter the name of the currency which will be used for {self.first_aux_currency} on the edge which connects {self.target_currency} to {self.first_aux_currency} >>> "

        self.assertEqual(expected, prompt)

    def test_replacement_source_bottom_prompt(self):
        triangular_arbitrage_config_map["second_aux_currency"].value = self.second_aux_currency
        triangular_arbitrage_config_map["first_aux_currency"].value = self.first_aux_currency

        prompt = replacement_source_bottom_prompt()
        expected = f"Enter the name of the currency which will be used for {self.first_aux_currency} on the edge which connects {self.first_aux_currency} to {self.second_aux_currency} >>> "

        self.assertEqual(expected, prompt)

    def test_replacement_target_bottom_prompt(self):
        triangular_arbitrage_config_map["second_aux_currency"].value = self.second_aux_currency
        triangular_arbitrage_config_map["first_aux_currency"].value = self.first_aux_currency

        prompt = replacement_target_bottom_prompt()
        expected = f"Enter the name of the currency which will be used for {self.second_aux_currency} on the edge which connects {self.first_aux_currency} to {self.second_aux_currency} >>> "

        self.assertEqual(expected, prompt)

    def test_replacement_source_right_prompt(self):
        triangular_arbitrage_config_map["target_currency"].value = self.target_currency
        triangular_arbitrage_config_map["second_aux_currency"].value = self.second_aux_currency

        prompt = replacement_source_right_prompt()
        expected = f"Enter the name of the currency which will be used for {self.second_aux_currency} on the edge which connects {self.second_aux_currency} to {self.target_currency} >>> "

        self.assertEqual(expected, prompt)

    def test_replacement_target_right_prompt(self):
        triangular_arbitrage_config_map["target_currency"].value = self.target_currency
        triangular_arbitrage_config_map["second_aux_currency"].value = self.second_aux_currency

        prompt = replacement_target_right_prompt()
        expected = f"Enter the name of the currency which will be used for {self.target_currency} on the edge which connects {self.second_aux_currency} to {self.target_currency} >>> "

        self.assertEqual(expected, prompt)
