# from hummingbot.client.command.import_command import ImportCommand
import unittest
# import asyncio
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.command.previous_strategy import PreviousCommand
# from hummingbot.client.command.previous_strategy import HummingbotApplication
# from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication
from unittest.mock import patch


class PreviousCommandUnitTest(unittest.TestCase):

    def mock_user_response(self, config):
        config.value = "yes"

    @patch.object(HummingbotApplication, '_notify')
    def test_no_previous_strategy_found(self, hummingbotApplication):
        safe_ensure_future(PreviousCommand.previous_statrategy(hummingbotApplication, option=""))
        hummingbotApplication._notify.assert_called()
        hummingbotApplication._notify.assert_called_with('No previous strategy found.')

    # @patch.object(HummingbotApplication, 'prompt_answer')
    # def test_strategy_found_and_user_declines(self, hummingbotApplication):
    #     strategy_name = "conf_1.yml"
    #     global_config_map["previous_strategy"].value = strategy_name
    #     hummingbotApplication.prompt_answer.side_effects = self.mock_user_response
    #     loop = asyncio.get_event_loop()
    #     loop.run_until_complete(safe_ensure_future(PreviousCommand.previous_statrategy(hummingbotApplication, option="")))
    #     hummingbotApplication._notify.assert_called()
    #     hummingbotApplication._notify.assert_called_with('No previous strategy found.')
