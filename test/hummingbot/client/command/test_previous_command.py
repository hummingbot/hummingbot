import asyncio
import unittest
from typing import Awaitable
from unittest.mock import MagicMock, patch

from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication

from test.mock.mock_cli import CLIMockingAssistant  # isort: skip


class PreviousCommandUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()

        self.async_run_with_timeout(read_system_configs_from_yml())
        self.app = HummingbotApplication()
        self.cli_mock_assistant = CLIMockingAssistant(self.app.app)
        self.cli_mock_assistant.start()

    def tearDown(self) -> None:
        self.cli_mock_assistant.stop()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def mock_user_response(self, config):
        config.value = "yes"

    def test_no_previous_strategy_found(self):
        global_config_map["previous_strategy"].value = None
        self.app.previous_strategy(option="")
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with("No previous strategy found."))

    @patch("hummingbot.client.command.import_command.ImportCommand.import_command")
    def test_strategy_found_and_user_declines(self, import_command: MagicMock):
        strategy_name = "conf_1.yml"
        self.cli_mock_assistant.queue_prompt_reply("No")
        self.async_run_with_timeout(
            self.app.prompt_for_previous_strategy(strategy_name)
        )
        import_command.assert_not_called()

    @patch("hummingbot.client.command.import_command.ImportCommand.import_command")
    def test_strategy_found_and_user_accepts(self, import_command: MagicMock):
        strategy_name = "conf_1.yml"
        global_config_map["previous_strategy"].value = strategy_name
        self.cli_mock_assistant.queue_prompt_reply("Yes")
        self.async_run_with_timeout(
            self.app.prompt_for_previous_strategy(strategy_name)
        )
        import_command.assert_called()
        self.assertTrue(import_command.call_args[0][1] == strategy_name)
