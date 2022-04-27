import asyncio
import unittest
from collections import Awaitable
from copy import deepcopy
from decimal import Decimal
from test.mock.mock_cli import CLIMockingAssistant
from unittest.mock import MagicMock, patch

from pydantic import Field

from hummingbot.client.command.config_command import color_settings_to_display, global_configs_to_display
from hummingbot.client.config.config_data_types import BaseClientModel, BaseStrategyConfigMap, ClientFieldData
from hummingbot.client.config.config_helpers import ClientConfigAdapter, read_system_configs_from_yml
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
        self.cli_mock_assistant = CLIMockingAssistant(self.app.app)
        self.cli_mock_assistant.start()
        self.global_config_backup = deepcopy(global_config_map)

    def tearDown(self) -> None:
        self.cli_mock_assistant.stop()
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
            "    +---------------------+---------+"
            "\n    | Key                 | Value   |"
            "\n    |---------------------+---------|"
            "\n    | tables_format       | psql    |"
            "\n    | autofill_import     | first   |"
            "\n    | kill_switch_enabled | second  |"
            "\n    +---------------------+---------+"
        )

        self.assertEqual(df_str_expected, captures[1])
        self.assertEqual("\nColor Settings:", captures[2])

        df_str_expected = (
            "    +-------------+---------+"
            "\n    | Key         | Value   |"
            "\n    |-------------+---------|"
            "\n    | top-pane    | third   |"
            "\n    | bottom-pane | fourth  |"
            "\n    +-------------+---------+"
        )

        self.assertEqual(df_str_expected, captures[3])
        self.assertEqual("\nStrategy Configurations:", captures[4])

        df_str_expected = (
            "    +-------+---------+"
            "\n    | Key   | Value   |"
            "\n    |-------+---------|"
            "\n    | five  | fifth   |"
            "\n    | six   | sixth   |"
            "\n    +-------+---------+"
        )

        self.assertEqual(df_str_expected, captures[5])

    @patch("hummingbot.client.hummingbot_application.get_strategy_config_map")
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication.notify")
    def test_list_configs_pydantic_model(self, notify_mock, get_strategy_config_map_mock):
        captures = []
        notify_mock.side_effect = lambda s: captures.append(s)
        strategy_name = "some-strategy"
        self.app.strategy_name = strategy_name

        tables_format_config_var = global_config_map["tables_format"]
        global_config_map.clear()
        global_config_map[tables_format_config_var.key] = tables_format_config_var
        tables_format_config_var.value = "psql"

        class DoubleNestedModel(BaseClientModel):
            double_nested_attr: float = Field(default=3.0)

            class Config:
                title = "double_nested_model"

        class NestedModel(BaseClientModel):
            nested_attr: str = Field(default="some value")
            double_nested_model: DoubleNestedModel = Field(default=DoubleNestedModel())

            class Config:
                title = "nested_model"

        class DummyModel(BaseClientModel):
            some_attr: int = Field(default=1)
            nested_model: NestedModel = Field(default=NestedModel())
            another_attr: Decimal = Field(default=Decimal("1.0"))
            missing_no_default: int = Field(default=...)

            class Config:
                title = "dummy_model"

        get_strategy_config_map_mock.return_value = ClientConfigAdapter(DummyModel.construct())

        self.app.list_configs()

        self.assertEqual(6, len(captures))

        self.assertEqual("\nStrategy Configurations:", captures[4])

        df_str_expected = (
            "    +------------------------+------------------------+"
            "\n    | Key                    | Value                  |"
            "\n    |------------------------+------------------------|"
            "\n    | some_attr              | 1                      |"
            "\n    | nested_model           | nested_model           |"
            "\n    | ∟ nested_attr          | some value             |"
            "\n    | ∟ double_nested_model  | double_nested_model    |"
            "\n    |   ∟ double_nested_attr | 3.0                    |"
            "\n    | another_attr           | 1.0                    |"
            "\n    | missing_no_default     | &cMISSING_AND_REQUIRED |"
            "\n    +------------------------+------------------------+"
        )

        self.assertEqual(df_str_expected, captures[5])

    @patch("hummingbot.client.hummingbot_application.get_strategy_config_map")
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication.notify")
    def test_config_non_configurable_key_fails(self, notify_mock, get_strategy_config_map_mock):
        class DummyModel(BaseStrategyConfigMap):
            strategy: str = Field(default="pure_market_making", client_data=None)
            some_attr: int = Field(default=1, client_data=ClientFieldData(prompt=lambda mi: "some prompt"))
            another_attr: Decimal = Field(default=Decimal("1.0"))

            class Config:
                title = "dummy_model"

        strategy_name = "some-strategy"
        self.app.strategy_name = strategy_name
        get_strategy_config_map_mock.return_value = ClientConfigAdapter(DummyModel.construct())
        self.app.config(key="some_attr")

        notify_mock.assert_not_called()

        self.app.config(key="another_attr")

        notify_mock.assert_called_once_with("Invalid key, please choose from the list.")

        notify_mock.reset_mock()
        self.app.config(key="some_key")

        notify_mock.assert_called_once_with("Invalid key, please choose from the list.")

    @patch("hummingbot.client.command.config_command.save_to_yml")
    @patch("hummingbot.client.hummingbot_application.get_strategy_config_map")
    @patch("hummingbot.client.hummingbot_application.HummingbotApplication.notify")
    def test_config_single_keys(self, _, get_strategy_config_map_mock, save_to_yml_mock):
        class NestedModel(BaseClientModel):
            nested_attr: str = Field(
                default="some value", client_data=ClientFieldData(prompt=lambda mi: "some prompt")
            )

            class Config:
                title = "nested_model"

        class DummyModel(BaseStrategyConfigMap):
            strategy: str = Field(default="pure_market_making", client_data=None)
            some_attr: int = Field(default=1, client_data=ClientFieldData(prompt=lambda mi: "some prompt"))
            nested_model: NestedModel = Field(default=NestedModel())

            class Config:
                title = "dummy_model"

        strategy_name = "some-strategy"
        self.app.strategy_name = strategy_name
        self.app.strategy_file_name = f"{strategy_name}.yml"
        config_map = ClientConfigAdapter(DummyModel.construct())
        get_strategy_config_map_mock.return_value = config_map

        self.async_run_with_timeout(self.app._config_single_key(key="some_attr", input_value=2))

        self.assertEqual(2, config_map.some_attr)
        save_to_yml_mock.assert_called_once()

        save_to_yml_mock.reset_mock()
        self.cli_mock_assistant.queue_prompt_reply("3")
        self.async_run_with_timeout(self.app._config_single_key(key="some_attr", input_value=None))

        self.assertEqual(3, config_map.some_attr)
        save_to_yml_mock.assert_called_once()

        save_to_yml_mock.reset_mock()
        self.cli_mock_assistant.queue_prompt_reply("another value")
        self.async_run_with_timeout(self.app._config_single_key(key="nested_model.nested_attr", input_value=None), 10000)

        self.assertEqual("another value", config_map.nested_model.nested_attr)
        save_to_yml_mock.assert_called_once()
