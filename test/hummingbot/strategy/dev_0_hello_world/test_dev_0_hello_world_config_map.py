import unittest

from copy import deepcopy

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.strategy.dev_0_hello_world.dev_0_hello_world_config_map import (
    asset_prompt,
    dev_0_hello_world_config_map,
    trading_pair_prompt,
)


class Dev0HelloWorldConfigMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.exchange = "binance"

    def setUp(self) -> None:
        super().setUp()
        self.config_backup = deepcopy(dev_0_hello_world_config_map)

    def tearDown(self) -> None:
        self.reset_config_map()
        super().tearDown()

    def reset_config_map(self):
        for key, value in self.config_backup.items():
            dev_0_hello_world_config_map[key] = value

    def test_trading_pair_prompt(self):
        dev_0_hello_world_config_map["exchange"].value = self.exchange
        example = AllConnectorSettings.get_example_pairs().get(self.exchange)

        prompt = trading_pair_prompt()
        expected = f"Enter the trading pair you would like to trade on {self.exchange} (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)

    def test_asset_prompt(self):
        dev_0_hello_world_config_map["exchange"].value = self.exchange
        example = AllConnectorSettings.get_example_assets().get(self.exchange)

        prompt = asset_prompt()
        expected = f"Enter a single token to fetch its balance on {self.exchange} (e.g. {example}) >>> "

        self.assertEqual(expected, prompt)
