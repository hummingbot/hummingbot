# from hummingbot.client.command.import_command import ImportCommand
import unittest
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.command.previous_strategy import PreviousCommand
# from hummingbot.client.command.previous_strategy import HummingbotApplication
# from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.hummingbot_application import HummingbotApplication
from unittest.mock import patch


class PreviousCommandUnitTest(unittest.TestCase):

    @patch.object(HummingbotApplication, '_notify')
    def test_message_prompt(self, hummingbotApplication):
        safe_ensure_future(PreviousCommand.previous_statrategy(hummingbotApplication, option=""))
        hummingbotApplication._notify.assert_called()
        hummingbotApplication._notify.assert_called_with('No previous strategy found.')
