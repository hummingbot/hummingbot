#!/usr/bin/env python

from os.path import (
    isdir,
    join,
    realpath,
)
from os import listdir
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))
import logging; logging.basicConfig(level=logging.INFO)
import unittest
import ruamel.yaml

from hummingbot.client.config.config_helpers import (
    get_strategy_template_path,
    get_strategy_config_map,
)
from hummingbot.client.config.global_config_map import global_config_map

yaml_parser = ruamel.yaml.YAML()


class ConfigTemplatesUnitTest(unittest.TestCase):

    def test_global_config_template(self):
        global_config_template_path: str = realpath(join(__file__, "../../hummingbot/templates/conf_global_TEMPLATE.yml"))

        with open(global_config_template_path, "r") as template_fd:
            template_data = yaml_parser.load(template_fd)
            template_version = template_data.get("template_version", 0)
            self.assertGreaterEqual(template_version, 1)
            for key in template_data:
                if key == "template_version":
                    continue
                self.assertTrue(key in global_config_map, f"{key} not in global_config_map")

    def test_strategy_config_template(self):
        folder = realpath(join(__file__, "../../hummingbot/strategy"))
        # Only include valid directories
        strategies = [d for d in listdir(folder) if isdir(join(folder, d)) and not d.startswith("__")]
        strategies.sort()

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
