import asyncio
import logging
import unittest.mock
from os.path import join

import ruamel.yaml

from hummingbot import root_path
from hummingbot.client.config.config_helpers import load_yml_into_cm
from hummingbot.client.config.config_var import ConfigVar

# Use ruamel.yaml to preserve order and comments in .yml file
yaml_parser = ruamel.yaml.YAML()
logger = logging.getLogger(__name__)

events = []


class ConfigHelpersTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

    def test_load_yml_into_cm_template_exception(self):
        loop = asyncio.get_event_loop()
        with self.assertLogs(level='ERROR') as log:
            loop.run_until_complete(load_yml_into_cm("", "", None))
            self.assertEqual("The template file was not found" in str(log.records[0]), True)

    def test_load_yml_into_cm_cm_exception(self):
        fee_overrides_config_template_path: str = join(root_path(),
                                                       "test/templates/conf_fee_overrides_TEMPLATE.yml")
        loop = asyncio.get_event_loop()
        with self.assertLogs(level='ERROR') as log:
            loop.run_until_complete(load_yml_into_cm("", fee_overrides_config_template_path, None))
            self.assertEqual("The configuration map file is None" in str(log.records[0]), 1)

    def test_load_yml_into_cm_cm_not_matching_template_exception(self):
        fee_overrides_config_template_path: str = join(root_path(),
                                                       "test/templates/conf_fee_overrides_TEMPLATE.yml")
        fee_overrides_config_map = {
            "binance_percent_fee_token": ConfigVar(key="binance_percent_fee_token", prompt="test prompt")}

        loop = asyncio.get_event_loop()
        with self.assertLogs(level='ERROR') as log:
            loop.run_until_complete(load_yml_into_cm("", fee_overrides_config_template_path, fee_overrides_config_map))
            self.assertEqual(
                "Cannot find corresponding config to key binance_maker_percent_fee in template" in str(log.records[0]),
                1)

    def test_load_yml_into_cm_conffile_missing_error(self):
        fee_overrides_config_template_path: str = join(root_path(),
                                                       "test/templates/conf_fee_overrides_TEMPLATE.yml")
        fee_overrides_config_map = {
            "binance_percent_fee_token": ConfigVar(key="binance_percent_fee_token", prompt="test prompt"),
            "binance_maker_percent_fee": ConfigVar(key="binance_maker_percent_fee", prompt="test prompt"),
            "binance_taker_percent_fee": ConfigVar(key="binance_taker_percent_fee", prompt="test prompt"),
            "binance_buy_percent_fee_deducted_from_returns": ConfigVar(
                key="binance_buy_percent_fee_deducted_from_returns",
                prompt="test prompt"),
            "altmarkets_buy_percent_fee_deducted_from_returns": ConfigVar(
                key="altmarkets_buy_percent_fee_deducted_from_returns", prompt="test prompt"),
            "altmarkets_maker_fixed_fees": ConfigVar(key="altmarkets_maker_fixed_fees", prompt="test prompt"),
            "altmarkets_maker_percent_fee": ConfigVar(key="altmarkets_maker_percent_fee", prompt="test prompt"),
            "altmarkets_percent_fee_token": ConfigVar(key="altmarkets_percent_fee_token", prompt="test prompt"),
            "altmarkets_taker_fixed_fees": ConfigVar(key="altmarkets_taker_fixed_fees", prompt="test prompt"),
            "altmarkets_taker_percent_fee": ConfigVar(key="altmarkets_taker_percent_fee", prompt="test prompt"),
            "kucoin_percent_fee_token": ConfigVar(key="kucoin_percent_fee_token", prompt="test prompt"),
            "kucoin_maker_percent_fee": ConfigVar(key="kucoin_maker_percent_fee", prompt="test prompt"),
            "kucoin_taker_percent_fee": ConfigVar(key="kucoin_taker_percent_fee", prompt="test prompt"),
            "kucoin_buy_percent_fee_deducted_from_returns": ConfigVar(
                key="kucoin_buy_percent_fee_deducted_from_returns",
                prompt="test prompt")}

        loop = asyncio.get_event_loop()
        with self.assertLogs(level='ERROR') as log:
            loop.run_until_complete(load_yml_into_cm("", fee_overrides_config_template_path, fee_overrides_config_map))
            self.assertEqual("The template file was not found" in str(log.records[0]), 1)

    def test_load_yml_into_cm_conffile_exception(self):
        fee_overrides_config_template_path: str = join(root_path(),
                                                       "test/templates/conf_fee_overrides_TEMPLATE.yml")
        fee_overrides_config_path: str = join(root_path(),
                                              "test/conf/conf_fee_overrides.yml")
        fee_overrides_config_map = {
            "binance_percent_fee_token": ConfigVar(key="binance_percent_fee_token", prompt="test prompt"),
            "binance_maker_percent_fee": ConfigVar(key="binance_maker_percent_fee", prompt="test prompt"),
            "binance_taker_percent_fee": ConfigVar(key="binance_taker_percent_fee", prompt="test prompt"),
            "binance_buy_percent_fee_deducted_from_returns": ConfigVar(
                key="binance_buy_percent_fee_deducted_from_returns",
                prompt="test prompt"),
            "altmarkets_buy_percent_fee_deducted_from_returns": ConfigVar(
                key="altmarkets_buy_percent_fee_deducted_from_returns", prompt="test prompt"),
            "altmarkets_maker_fixed_fees": ConfigVar(key="altmarkets_maker_fixed_fees", prompt="test prompt"),
            "altmarkets_maker_percent_fee": ConfigVar(key="altmarkets_maker_percent_fee", prompt="test prompt"),
            "altmarkets_percent_fee_token": ConfigVar(key="altmarkets_percent_fee_token", prompt="test prompt"),
            "altmarkets_taker_fixed_fees": ConfigVar(key="altmarkets_taker_fixed_fees", prompt="test prompt"),
            "altmarkets_taker_percent_fee": ConfigVar(key="altmarkets_taker_percent_fee", prompt="test prompt"),
            "kucoin_percent_fee_token": ConfigVar(key="kucoin_percent_fee_token", prompt="test prompt"),
            "kucoin_maker_percent_fee": ConfigVar(key="kucoin_maker_percent_fee", prompt="test prompt"),
            "kucoin_taker_percent_fee": ConfigVar(key="kucoin_taker_percent_fee", prompt="test prompt"),
            "kucoin_buy_percent_fee_deducted_from_returns": ConfigVar(
                key="kucoin_buy_percent_fee_deducted_from_returns",
                prompt="test prompt")}

        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            load_yml_into_cm(fee_overrides_config_path, fee_overrides_config_template_path, fee_overrides_config_map))
        var = fee_overrides_config_map.get("kucoin_percent_fee_token")
        self.assertEqual(var.value, "KCS")
        var = fee_overrides_config_map.get("altmarkets_buy_percent_fee_deducted_from_returns")
        self.assertEqual(var.value, None)
