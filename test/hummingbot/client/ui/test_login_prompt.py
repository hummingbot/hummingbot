import asyncio
import unittest
from copy import deepcopy
from unittest.mock import MagicMock, patch

from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.ui import login_prompt
from hummingbot.client.ui.style import load_style


class LoginPromptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.ev_loop.run_until_complete(read_system_configs_from_yml())

    def setUp(self) -> None:
        super().setUp()
        self.global_config_backup = deepcopy(global_config_map)

    def tearDown(self) -> None:
        self.reset_global_config()
        super().tearDown()

    def reset_global_config(self):
        for key, value in self.global_config_backup.items():
            global_config_map[key] = value

    @patch("hummingbot.client.ui.message_dialog")
    @patch("hummingbot.client.ui.input_dialog")
    @patch("hummingbot.client.config.security.Security.login")
    @patch("hummingbot.client.config.security.Security.new_password_required")
    def test_login_success(
        self,
        new_password_required_mock: MagicMock,
        login_mock: MagicMock,
        input_dialog_mock: MagicMock,
        message_dialog_mock: MagicMock,
    ):
        new_password_required_mock.return_value = False
        run_mock = MagicMock()
        run_mock.run.return_value = "somePassword"
        input_dialog_mock.return_value = run_mock
        login_mock.return_value = True

        self.assertTrue(login_prompt(style=load_style()))
        self.assertEqual(1, len(login_mock.mock_calls))
        message_dialog_mock.assert_not_called()

    @patch("hummingbot.client.ui.message_dialog")
    @patch("hummingbot.client.ui.input_dialog")
    @patch("hummingbot.client.config.security.Security.login")
    @patch("hummingbot.client.config.security.Security.new_password_required")
    def test_login_error_retries(
        self,
        new_password_required_mock: MagicMock,
        login_mock: MagicMock,
        input_dialog_mock: MagicMock,
        message_dialog_mock: MagicMock,
    ):
        new_password_required_mock.return_value = False
        run_mock = MagicMock()
        run_mock.run.return_value = "somePassword"
        input_dialog_mock.return_value = run_mock
        message_dialog_mock.return_value = run_mock
        login_mock.side_effect = [False, True]

        self.assertTrue(login_prompt(style=load_style()))
        self.assertEqual(2, len(login_mock.mock_calls))
        message_dialog_mock.assert_called()
