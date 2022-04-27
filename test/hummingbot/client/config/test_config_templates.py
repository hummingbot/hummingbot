import unittest
from os.path import join

import ruamel.yaml

from hummingbot import root_path
from hummingbot.client.config.config_helpers import get_strategy_config_map, get_strategy_template_path
from hummingbot.client.config.global_config_map import global_config_map

import logging; logging.basicConfig(level=logging.INFO)


yaml_parser = ruamel.yaml.YAML()


class ConfigTemplatesUnitTest(unittest.TestCase):

    def test_global_config_template_complete(self):
        global_config_template_path: str = join(root_path(), "hummingbot/templates/conf_global_TEMPLATE.yml")

        with open(global_config_template_path, "r") as template_fd:
            template_data = yaml_parser.load(template_fd)
            template_version = template_data.get("template_version", 0)
            self.assertGreaterEqual(template_version, 1)
            for key in template_data:
                if key == "template_version":
                    continue
                self.assertTrue(key in global_config_map, f"{key} not in global_config_map")

            for key in global_config_map:
                self.assertTrue(key in template_data, f"{key} not in {global_config_template_path}")

    def test_strategy_config_template_complete_legacy(self):
        strategies = [  # templates is a legacy approach — new strategies won't use it
            "amm_arb",
            "arbitrage",
            "aroon_oscillator",
            "celo_arb",
            "cross_exchange_market_making",
            "dev_0_hello_world",
            "dev_1_get_order_book",
            "dev_2_perform_trade",
            "dev_5_vwap",
            "dev_simple_trade",
            "hedge",
            "liquidity_mining",
            "perpetual_market_making",
            "pure_market_making",
            "spot_perpetual_arbitrage",
            "twap",
        ]

        for strategy in strategies:
            strategy_template_path: str = get_strategy_template_path(strategy)
            strategy_config_map = get_strategy_config_map(strategy)

            with open(strategy_template_path, "r") as template_fd:
                template_data = yaml_parser.load(template_fd)
                template_version = template_data.get("template_version", 0)
                self.assertGreaterEqual(template_version, 1, f"Template version too low at {strategy_template_path}")
                for key in template_data:
                    if key == "template_version":
                        continue
                    self.assertTrue(key in strategy_config_map, f"{key} not in {strategy}_config_map")

                for key in strategy_config_map:
                    self.assertTrue(key in template_data, f"{key} not in {strategy_template_path}")

    def test_global_config_prompt_exists(self):
        for key in global_config_map:
            cvar = global_config_map[key]
            if cvar.required:
                self.assertTrue(cvar.prompt is not None)
