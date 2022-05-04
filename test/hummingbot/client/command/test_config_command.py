import asyncio
import unittest
from collections import Awaitable
from copy import deepcopy
from unittest.mock import patch, MagicMock

from hummingbot.client.command.config_command import color_settings_to_display, global_configs_to_display
from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication


class ConfigCommandTest(unittest.TestCase):
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher")
    def setUp(self, _: MagicMock) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

        self.async_run_with_timeout(read_system_configs_from_yml())

        self.app = HummingbotApplication()
        self.global_config_backup = deepcopy(global_config_map)

    def tearDown(self) -> None:
        self.reset_global_config()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def reset_global_config(self):
        for key, value in self.global_config_backup.items():
            global_config_map[key] = value

    @patch("hummingbot.client.hummingbot_application.get_strategy_config_map")
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication.notify")
    def test_list_configs(self, notify_mock, get_strategy_config_map_mock):
        captures = []
        notify_mock.side_effect = lambda s: captures.append(s)
        strategy_name = "some-strategy"
        self.app.strategy_name = strategy_name

        tables_format_config_var = global_config_map["tables_format"]
        global_config_map.clear()
        global_config_map[tables_format_config_var.key] = tables_format_config_var
        tables_format_config_var.value = "psql"
        global_config_map[global_configs_to_display[0]] = ConfigVar(key=global_configs_to_display[0], prompt="")
        global_config_map[global_configs_to_display[0]].value = "first"
        global_config_map[global_configs_to_display[1]] = ConfigVar(key=global_configs_to_display[1], prompt="")
        global_config_map[global_configs_to_display[1]].value = "second"
        global_config_map[color_settings_to_display[0]] = ConfigVar(key=color_settings_to_display[0], prompt="")
        global_config_map[color_settings_to_display[0]].value = "third"
        global_config_map[color_settings_to_display[1]] = ConfigVar(key=color_settings_to_display[1], prompt="")
        global_config_map[color_settings_to_display[1]].value = "fourth"
        strategy_config_map_mock = {
            "five": ConfigVar(key="five", prompt=""),
            "six": ConfigVar(key="six", prompt="", default="sixth"),
        }
        strategy_config_map_mock["five"].value = "fifth"
        strategy_config_map_mock["six"].value = "sixth"
        get_strategy_config_map_mock.return_value = strategy_config_map_mock

        self.app.list_configs()

        self.assertEqual(6, len(captures))
        self.assertEqual("\nGlobal Configurations:", captures[0])

        df_str_expected = (
            "    +---------------------+-----------+"
            "\n    | Key                 |   Value   |"
            "\n    |---------------------+-----------|"
            "\n    | tables_format       | psql      |"
            "\n    | autofill_import     | first     |"
            "\n    | kill_switch_enabled | second    |"
            "\n    +---------------------+-----------+"
        )

        self.assertEqual(df_str_expected, captures[1])
        self.assertEqual("\nColor Settings:", captures[2])

        df_str_expected = (
            "    +-------------+-----------+"
            "\n    | Key         |   Value   |"
            "\n    |-------------+-----------|"
            "\n    | top-pane    | third     |"
            "\n    | bottom-pane | fourth    |"
            "\n    +-------------+-----------+"
        )

        self.assertEqual(df_str_expected, captures[3])
        self.assertEqual("\nStrategy Configurations:", captures[4])

        df_str_expected = (
            "    +-------+-----------+"
            "\n    | Key   |   Value   |"
            "\n    |-------+-----------|"
            "\n    | five  | fifth     |"
            "\n    | six   | sixth     |"
            "\n    +-------+-----------+"
        )

        self.assertEqual(df_str_expected, captures[5])
