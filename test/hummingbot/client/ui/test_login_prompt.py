import unittest
from unittest.mock import MagicMock, patch

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.ui import login_prompt
from hummingbot.client.ui.style import load_style


class LoginPromptTest(unittest.TestCase):
    # @classmethod
    # def setUpClass(cls) -> None:
    #     super().setUpClass()
    #     cls.ev_loop = asyncio.get_event_loop()
    #     cls.ev_loop.run_until_complete(read_system_configs_from_yml())

    def setUp(self) -> None:
        super().setUp()
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.password = "som-password"

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
        run_mock.run.return_value = self.password
        input_dialog_mock.return_value = run_mock
        login_mock.return_value = True

        self.assertTrue(login_prompt(ETHKeyFileSecretManger, style=load_style(self.client_config_map)))
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

        self.assertTrue(login_prompt(ETHKeyFileSecretManger, style=load_style(self.client_config_map)))
        self.assertEqual(2, len(login_mock.mock_calls))
        message_dialog_mock.assert_called()

    @patch("hummingbot.client.ui.message_dialog")
    @patch("hummingbot.client.ui.input_dialog")
    @patch("hummingbot.client.config.security.Security.new_password_required")
    def test_iterate_or_skip_through_blank_password(
        self,
        new_password_required_mock: MagicMock,
        input_dialog_mock: MagicMock,
        message_dialog_mock: MagicMock,
    ):
        new_password_required_mock.return_value = True
        run_mock = MagicMock()
        run_mock.run.return_value = None
        input_dialog_mock.return_value = run_mock
        message_dialog_mock.return_value = run_mock

        self.assertEqual(login_prompt(ETHKeyFileSecretManger, style=load_style(self.client_config_map)), None)

        run_mock.run.return_value = str()
        self.assertEqual(login_prompt(ETHKeyFileSecretManger, style=load_style(self.client_config_map)), None)
