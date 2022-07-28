import unittest
from copy import deepcopy

from hummingbot.client.settings import AllConnectorSettings, required_exchanges
from hummingbot.strategy.fixed_grid.fixed_grid_config_map import (
    exchange_on_validated,
    fixed_grid_config_map,
    maker_trading_pair_prompt,
    order_amount_prompt,
)


class TestFixedGridConfigMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.exchange = "binance"
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        required_exchanges.clear()
        self.config_backup = deepcopy(fixed_grid_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        required_exchanges.clear()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            fixed_grid_config_map[key] = value

    def test_order_amount_prompt(self):
        fixed_grid_config_map["market"].value = self.trading_pair
        prompt = order_amount_prompt()
        expected = f"What is the amount of {self.base_asset} per order? >>> "

        self.assertEqual(expected, prompt)

    def test_maker_trading_pair_prompt(self):
        fixed_grid_config_map["exchange"].value = self.exchange
        example = AllConnectorSettings.get_example_pairs().get(self.exchange)

        prompt = maker_trading_pair_prompt()
        expected = f"Enter the token trading pair you would like to trade on {self.exchange} (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)

    def test_exchange_on_validated(self):
        exchange_on_validated(self.exchange)
        expected_required_exchanges = {self.exchange}
        self.assertEqual(expected_required_exchanges, required_exchanges)
