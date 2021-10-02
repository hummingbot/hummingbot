# from hummingbot.client.command.import_command import ImportCommand
import unittest
import asyncio
# from hummingbot.core.utils.async_utils import safe_ensure_future
# from hummingbot.client.command.previous_strategy import PreviousCommand
# from hummingbot.client.command.previous_strategy import HummingbotApplication
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication
# from unittest.mock import patch, MagicMock, AsyncMock
from typing import Awaitable
# from unittest import IsolatedAsyncioTestCase
from test.mock.mock_cli import CLIMockingAssistant


class PreviousCommandUnitTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.ev_loop = asyncio.get_event_loop()
        self.app = HummingbotApplication()
        self.cli_mock_assistant = CLIMockingAssistant()
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
        self.app.previous_statrategy(option="")
        self.assertTrue(
            self.cli_mock_assistant.check_log_called_with("No previous strategy found."))

    # @patch.object(HummingbotApplication, '_notify')
    # @patch('HummingbotApplication')
    # def test_strategy_found_and_user_declines(self):
    #     # hummingbotApplication = Mock(spec=HummingbotApplication)
    #     strategy_name = "conf_1.yml"
    #     global_config_map["previous_strategy"].value = strategy_name
    #     self.async_run_with_timeout(self.app.previous_statrategy(option=""))
    #     self.assertEqual(strategy_name, self.app.strategy_name)
        # hummingbotApplication.prompt_answer.side_effects = self.mock_user_response
        # loop = asyncio.get_event_loop()
        # loop.run_until_complete(safe_ensure_future(PreviousCommand.previous_statrategy(hummingbotApplication, option="")))
        # task = PreviousCommand.previous_statrategy(app, option="")
        # await task
        # # task._result()
        # hummingbotApplication._notify.assert_called()
        # hummingbotApplication._notify.assert_called_with('No previous strategy found.')
        # with patch.object(HummingbotApplication, "_notify") as submethod_mocked:
        #     submethod_mocked
        # submethod_mocked.return_value = 13
        # MyClassUnderTest().main_method()
