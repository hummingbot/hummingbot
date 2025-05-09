import asyncio
import unittest
from unittest.mock import MagicMock, patch

from prompt_toolkit.widgets import Button

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter, read_system_configs_from_yml
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.tab.data_types import CommandTab
from hummingbot.client.ui.custom_widgets import CustomTextArea
from hummingbot.client.ui.hummingbot_cli import HummingbotCLI
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import HummingbotUIEvent


class HummingbotCLITest(unittest.TestCase):
    command_name = "command_1"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.ev_loop.run_until_complete(read_system_configs_from_yml())

    def setUp(self) -> None:
        super().setUp()

        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        tabs = {self.command_name: CommandTab(self.command_name, None, None, None, MagicMock())}
        self.mock_hb = MagicMock()
        self.app = HummingbotCLI(
            client_config_map=self.client_config_map,
            input_handler=None,
            bindings=None,
            completer=None,
            command_tabs=tabs)
        self.app.app = MagicMock()
        self.hb = HummingbotApplication()

    def test_handle_tab_command_on_close_argument(self):
        tab = self.app.command_tabs[self.command_name]
        tab.close_button = MagicMock()
        tab.button = MagicMock()
        tab.output_field = MagicMock()
        self.app.handle_tab_command(self.mock_hb, self.command_name, {"close": True})
        self.assertIsNone(tab.button)
        self.assertIsNone(tab.close_button)
        self.assertIsNone(tab.output_field)
        self.assertFalse(tab.is_selected)
        self.assertEqual(tab.tab_index, 0)

    def test_handle_tab_command_create_new_tab_and_display(self):
        tab = self.app.command_tabs[self.command_name]
        self.app.handle_tab_command(self.mock_hb, self.command_name, {"close": False})
        self.assertIsInstance(tab.button, Button)
        self.assertIsInstance(tab.close_button, Button)
        self.assertIsInstance(tab.output_field, CustomTextArea)
        self.assertEqual(tab.tab_index, 1)
        self.assertTrue(tab.is_selected)
        self.assertTrue(tab.tab_class.display.called)

    @patch("hummingbot.client.ui.layout.Layout")
    @patch("hummingbot.client.ui.layout.FloatContainer")
    @patch("hummingbot.client.ui.layout.ConditionalContainer")
    @patch("hummingbot.client.ui.layout.Box")
    @patch("hummingbot.client.ui.layout.HSplit")
    @patch("hummingbot.client.ui.layout.VSplit")
    def test_handle_tab_command_on_existing_tab(self, mock_vsplit, mock_hsplit, mock_box, moc_cc, moc_fc, mock_layout):
        tab = self.app.command_tabs[self.command_name]
        tab.button = MagicMock()
        tab.output_field = MagicMock()
        tab.close_button = MagicMock()
        tab.is_selected = False
        self.app.handle_tab_command(self.mock_hb, self.command_name, {"close": False})
        self.assertTrue(tab.is_selected)
        self.assertTrue(tab.tab_class.display.call_count == 1)

        # Test display not called if there is a running task
        tab.is_selected = False
        tab.task = MagicMock()
        tab.task.done.return_value = False
        self.app.handle_tab_command(self.mock_hb, self.command_name, {"close": False})
        self.assertTrue(tab.is_selected)
        self.assertTrue(tab.tab_class.display.call_count == 1)

    @patch("hummingbot.client.ui.layout.Layout")
    @patch("hummingbot.client.ui.layout.FloatContainer")
    @patch("hummingbot.client.ui.layout.ConditionalContainer")
    @patch("hummingbot.client.ui.layout.Box")
    @patch("hummingbot.client.ui.layout.HSplit")
    @patch("hummingbot.client.ui.layout.VSplit")
    def test_tab_navigation(self, mock_vsplit, mock_hsplit, mock_box, moc_cc, moc_fc, mock_layout):
        tab2 = CommandTab("command_2", None, None, None, MagicMock(), False)

        self.app.command_tabs["command_2"] = tab2
        tab1 = self.app.command_tabs[self.command_name]

        self.app.handle_tab_command(self.mock_hb, self.command_name, {"close": False})
        self.app.handle_tab_command(self.mock_hb, "command_2", {"close": False})
        self.assertTrue(tab2.is_selected)

        self.app.tab_navigate_left()
        self.assertTrue(tab1.is_selected)
        self.assertFalse(tab2.is_selected)
        self.app.tab_navigate_left()
        self.assertTrue(all(not t.is_selected for t in self.app.command_tabs.values()))
        self.app.tab_navigate_left()
        self.assertTrue(all(not t.is_selected for t in self.app.command_tabs.values()))

        self.app.tab_navigate_right()
        self.assertTrue(tab1.is_selected)

        self.app.tab_navigate_right()
        self.assertFalse(tab1.is_selected)
        self.assertTrue(tab2.is_selected)

        self.app.tab_navigate_right()
        self.assertFalse(tab1.is_selected)
        self.assertTrue(tab2.is_selected)

    @patch("hummingbot.client.ui.hummingbot_cli.init_logging")
    def test_did_start_ui(self, mock_init_logging: MagicMock):
        class UIStartHandler(EventListener):
            def __init__(self):
                super().__init__()
                self.mock = MagicMock()

            def __call__(self, _):
                self.mock()

        handler: UIStartHandler = UIStartHandler()
        self.app.add_listener(HummingbotUIEvent.Start, handler)
        self.app.did_start_ui()

        mock_init_logging.assert_called()
        handler.mock.assert_called()
