import asyncio
import unittest

from prompt_toolkit.styles import Style
from typing import Awaitable
from unittest.mock import patch

from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.client.ui.style import load_style, reset_style, hex_to_ansi


class StyleTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUpClass()

        self.ev_loop = asyncio.get_event_loop()
        self.async_run_with_timeout(read_system_configs_from_yml())

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    class ConfigVar:
        value = None
        default = None

        def __init__(self, value, default=None):
            self.value = value
            self.default = default

    @patch("hummingbot.client.ui.style.is_windows")
    def test_load_style_unix(self, is_windows_mock):
        is_windows_mock.return_value = False

        global_config_map = {}
        global_config_map["top-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["bottom-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["output-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["input-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["logs-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["terminal-primary"] = self.ConfigVar("#FCFCFC")

        global_config_map["primary-label"] = self.ConfigVar("#5FFFD7")
        global_config_map["secondary-label"] = self.ConfigVar("#FFFFFF")
        global_config_map["success-label"] = self.ConfigVar("#5FFFD7")
        global_config_map["warning-label"] = self.ConfigVar("#FFFF00")
        global_config_map["info-label"] = self.ConfigVar("#5FD7FF")
        global_config_map["error-label"] = self.ConfigVar("#FF0000")

        style = Style.from_dict(
            {
                "output-field": "bg:#FAFAFA #FCFCFC",
                "input-field": "bg:#FAFAFA #FFFFFF",
                "log-field": "bg:#FAFAFA #FFFFFF",
                "header": "bg:#FAFAFA #AAAAAA",
                "footer": "bg:#FAFAFA #AAAAAA",
                "search": "bg:#000000 #93C36D",
                "search.current": "bg:#000000 #1CD085",
                "primary": "#FCFCFC",
                "warning": "#93C36D",
                "error": "#F5634A",
                # Label bg and font color
                "primary-label": "bg:#5FFFD7 #FAFAFA",
                "secondary-label": "bg:#FFFFFF #FAFAFA",
                "success-label": "bg:#5FFFD7 #FAFAFA",
                "warning-label": "bg:#FFFF00 #FAFAFA",
                "info-label": "bg:#5FD7FF #FAFAFA",
                "error-label": "bg:#FF0000 #FAFAFA",
            }
        )

        self.assertEqual(style.class_names_and_attrs, load_style(global_config_map).class_names_and_attrs)

    @patch("hummingbot.client.ui.style.is_windows")
    def test_load_style_windows(self, is_windows_mock):
        is_windows_mock.return_value = True

        global_config_map = {}
        global_config_map["top-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["bottom-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["output-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["input-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["logs-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["terminal-primary"] = self.ConfigVar("#FCFCFC")

        global_config_map["primary-label"] = self.ConfigVar("#5FFFD7")
        global_config_map["secondary-label"] = self.ConfigVar("#FFFFFF")
        global_config_map["success-label"] = self.ConfigVar("#5FFFD7")
        global_config_map["warning-label"] = self.ConfigVar("#FFFF00")
        global_config_map["info-label"] = self.ConfigVar("#5FD7FF")
        global_config_map["error-label"] = self.ConfigVar("#FF0000")

        style = Style.from_dict(
            {
                "output-field": "bg:#ansigray #ansigray",
                "input-field": "bg:#ansigray #ansiwhite",
                "log-field": "bg:#ansigray #ansiwhite",
                "header": "bg:#ansigray #ansiwhite",
                "footer": "bg:#ansigray #ansiwhite",
                "search": "#ansigray",
                "search.current": "#ansigray",
                "primary": "#ansigray",
                "warning": "#ansibrightyellow",
                "error": "#ansired",
                # Label bg and font color
                "primary-label": "bg:#ansicyan #ansigray",
                "secondary-label": "bg:#ansigray #ansigray",
                "success-label": "bg:#ansicyan #ansigray",
                "warning-label": "bg:#ansiyellow #ansigray",
                "info-label": "bg:#ansicyan #ansigray",
                "error-label": "bg:#ansired #ansigray",
            }
        )

        self.assertEqual(style.class_names_and_attrs, load_style(global_config_map).class_names_and_attrs)

    def test_reset_style(self):

        global_config_map = {}
        global_config_map["top-pane"] = self.ConfigVar("#FAFAFA", "#333333")
        global_config_map["bottom-pane"] = self.ConfigVar("#FAFAFA", "#333333")
        global_config_map["output-pane"] = self.ConfigVar("#FAFAFA", "#333333")
        global_config_map["input-pane"] = self.ConfigVar("#FAFAFA", "#333333")
        global_config_map["logs-pane"] = self.ConfigVar("#FAFAFA", "#333333")
        global_config_map["terminal-primary"] = self.ConfigVar("#FCFCFC", "#010101")

        global_config_map["primary-label"] = self.ConfigVar("#FAFAFA", "#5FFFD7")
        global_config_map["secondary-label"] = self.ConfigVar("#FAFAFA", "#FFFFFF")
        global_config_map["success-label"] = self.ConfigVar("#FAFAFA", "#5FFFD7")
        global_config_map["warning-label"] = self.ConfigVar("#FAFAFA", "#FFFF00")
        global_config_map["info-label"] = self.ConfigVar("#FAFAFA", "#5FD7FF")
        global_config_map["error-label"] = self.ConfigVar("#FAFAFA", "#FF0000")
        style = Style.from_dict(
            {
                "output-field": "bg:#333333 #010101",
                "input-field": "bg:#333333 #FFFFFF",
                "log-field": "bg:#333333 #FFFFFF",
                "header": "bg:#333333 #AAAAAA",
                "footer": "bg:#333333 #AAAAAA",
                "search": "bg:#000000 #93C36D",
                "search.current": "bg:#000000 #1CD085",
                "primary": "#010101",
                "warning": "#93C36D",
                "error": "#F5634A",
                # Label bg and font color
                "primary-label": "bg:#5FFFD7 #333333",
                "secondary-label": "bg:#FFFFFF #333333",
                "success-label": "bg:#5FFFD7 #333333",
                "warning-label": "bg:#FFFF00 #333333",
                "info-label": "bg:#5FD7FF #333333",
                "error-label": "bg:#FF0000 #333333",
            }
        )

        self.assertEqual(style.class_names_and_attrs, reset_style(config_map=global_config_map, save=False).class_names_and_attrs)

    def test_hex_to_ansi(self):
        self.assertEqual("#ansiblack", hex_to_ansi("#000000"))
        self.assertEqual("#ansired", hex_to_ansi("#FF0000"))
        self.assertEqual("#ansigreen", hex_to_ansi("#00FF00"))
        self.assertEqual("#ansiyellow", hex_to_ansi("#FFFF00"))
        self.assertEqual("#ansiblue", hex_to_ansi("#0000FF"))
        self.assertEqual("#ansimagenta", hex_to_ansi("#FF00FF"))
        self.assertEqual("#ansicyan", hex_to_ansi("#00FFFF"))
        self.assertEqual("#ansigray", hex_to_ansi("#F0F0F0"))

        self.assertEqual("#ansiyellow", hex_to_ansi("#FFFF00"))
        self.assertEqual("#ansiyellow", hex_to_ansi("#FFAA00"))
        self.assertEqual("#ansiyellow", hex_to_ansi("#FFFF00"))
        self.assertEqual("#ansired", hex_to_ansi("#FF1100"))

        self.assertEqual("#ansiyellow", hex_to_ansi("#ffff00"))
        self.assertEqual("#ansiyellow", hex_to_ansi("#ffaa00"))
        self.assertEqual("#ansiyellow", hex_to_ansi("#ffff00"))
        self.assertEqual("#ansired", hex_to_ansi("#ff1100"))

        self.assertEqual("#ansiyellow", hex_to_ansi("ffff00"))
