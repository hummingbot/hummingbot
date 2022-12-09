import unittest
from unittest.mock import patch

from prompt_toolkit.styles import Style

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.ui.style import hex_to_ansi, load_style, reset_style


class StyleTest(unittest.TestCase):
    class ConfigVar:
        value = None
        default = None

        def __init__(self, value, default=None):
            self.value = value
            self.default = default

    @patch("hummingbot.client.ui.style.is_windows")
    def test_load_style_unix(self, is_windows_mock):
        is_windows_mock.return_value = False

        global_config_map = ClientConfigMap()
        global_config_map.color.top_pane = "#FAFAFA"
        global_config_map.color.bottom_pane = "#FAFAFA"
        global_config_map.color.output_pane = "#FAFAFA"
        global_config_map.color.input_pane = "#FAFAFA"
        global_config_map.color.logs_pane = "#FAFAFA"
        global_config_map.color.terminal_primary = "#FCFCFC"

        global_config_map.color.primary_label = "#5FFFD7"
        global_config_map.color.secondary_label = "#FFFFFF"
        global_config_map.color.success_label = "#5FFFD7"
        global_config_map.color.warning_label = "#FFFF00"
        global_config_map.color.info_label = "#5FD7FF"
        global_config_map.color.error_label = "#FF0000"

        adapter = ClientConfigAdapter(global_config_map)

        style = Style.from_dict(
            {
                "output_field": "bg:#FAFAFA #FCFCFC",
                "input_field": "bg:#FAFAFA #FFFFFF",
                "log_field": "bg:#FAFAFA #FFFFFF",
                "header": "bg:#FAFAFA #AAAAAA",
                "footer": "bg:#FAFAFA #AAAAAA",
                "search": "bg:#000000 #93C36D",
                "search.current": "bg:#000000 #1CD085",
                "primary": "#FCFCFC",
                "warning": "#93C36D",
                "error": "#F5634A",
                "tab_button.focused": "bg:#FCFCFC #FAFAFA",
                "tab_button": "bg:#FFFFFF #FAFAFA",
                "dialog": "bg:#171E2B",
                "dialog frame.label": "bg:#FCFCFC #000000",
                "dialog.body": "bg:#000000 #FCFCFC",
                "dialog shadow": "bg:#171E2B",
                "button": "bg:#000000",
                "text-area": "bg:#000000 #FCFCFC",
                # Label bg and font color
                "primary_label": "bg:#5FFFD7 #FAFAFA",
                "secondary_label": "bg:#FFFFFF #FAFAFA",
                "success_label": "bg:#5FFFD7 #FAFAFA",
                "warning_label": "bg:#FFFF00 #FAFAFA",
                "info_label": "bg:#5FD7FF #FAFAFA",
                "error_label": "bg:#FF0000 #FAFAFA",
            }
        )

        self.assertEqual(style.class_names_and_attrs, load_style(adapter).class_names_and_attrs)

    @patch("hummingbot.client.ui.style.is_windows")
    def test_load_style_windows(self, is_windows_mock):
        is_windows_mock.return_value = True

        global_config_map = ClientConfigMap()
        global_config_map.color.top_pane = "#FAFAFA"
        global_config_map.color.bottom_pane = "#FAFAFA"
        global_config_map.color.output_pane = "#FAFAFA"
        global_config_map.color.input_pane = "#FAFAFA"
        global_config_map.color.logs_pane = "#FAFAFA"
        global_config_map.color.terminal_primary = "#FCFCFC"

        global_config_map.color.primary_label = "#5FFFD7"
        global_config_map.color.secondary_label = "#FFFFFF"
        global_config_map.color.success_label = "#5FFFD7"
        global_config_map.color.warning_label = "#FFFF00"
        global_config_map.color.info_label = "#5FD7FF"
        global_config_map.color.error_label = "#FF0000"

        adapter = ClientConfigAdapter(global_config_map)

        style = Style.from_dict(
            {
                "output_field": "bg:#ansiwhite #ansiwhite",
                "input_field": "bg:#ansiwhite #ansiwhite",
                "log_field": "bg:#ansiwhite #ansiwhite",
                "header": "bg:#ansiwhite #ansiwhite",
                "footer": "bg:#ansiwhite #ansiwhite",
                "search": "#ansiwhite",
                "search.current": "#ansiwhite",
                "primary": "#ansiwhite",
                "warning": "#ansibrightyellow",
                "error": "#ansired",
                "tab_button.focused": "bg:#ansiwhite #ansiwhite",
                "tab_button": "bg:#ansiwhite #ansiwhite",
                "dialog": "bg:#ansigreen",
                "dialog frame.label": "bg:#ansiwhite #ansiblack",
                "dialog.body": "bg:#ansiblack #ansiwhite",
                "dialog shadow": "bg:#ansigreen",
                "button": "bg:#ansigreen",
                "text-area": "bg:#ansiblack #ansiwhite",
                # Label bg and font color
                "primary_label": "bg:#ansicyan #ansiwhite",
                "secondary_label": "bg:#ansiwhite #ansiwhite",
                "success_label": "bg:#ansicyan #ansiwhite",
                "warning_label": "bg:#ansiyellow #ansiwhite",
                "info_label": "bg:#ansicyan #ansiwhite",
                "error_label": "bg:#ansired #ansiwhite",

            }
        )

        self.assertEqual(style.class_names_and_attrs, load_style(adapter).class_names_and_attrs)

    def test_reset_style(self):
        global_config_map = ClientConfigMap()
        global_config_map.color.top_pane = "#FAFAFA"
        global_config_map.color.bottom_pane = "#FAFAFA"
        global_config_map.color.output_pane = "#FAFAFA"
        global_config_map.color.input_pane = "#FAFAFA"
        global_config_map.color.logs_pane = "#FAFAFA"
        global_config_map.color.terminal_primary = "#FCFCFC"

        global_config_map.color.primary_label = "#FAFAFA"
        global_config_map.color.secondary_label = "#FAFAFA"
        global_config_map.color.success_label = "#FAFAFA"
        global_config_map.color.warning_label = "#FAFAFA"
        global_config_map.color.info_label = "#FAFAFA"
        global_config_map.color.error_label = "#FAFAFA"

        adapter = ClientConfigAdapter(global_config_map)

        style = Style.from_dict(
            {
                "output_field": "bg:#262626 #5FFFD7",
                "input_field": "bg:#1C1C1C #FFFFFF",
                "log_field": "bg:#121212 #FFFFFF",
                "header": "bg:#000000 #AAAAAA",
                "footer": "bg:#000000 #AAAAAA",
                "search": "bg:#000000 #93C36D",
                "search.current": "bg:#000000 #1CD085",
                "primary": "#5FFFD7",
                "warning": "#93C36D",
                "error": "#F5634A",
                "tab_button.focused": "bg:#5FFFD7 #121212",
                "tab_button": "bg:#FFFFFF #121212",
                "dialog": "bg:#171E2B",
                "dialog frame.label": "bg:#5FFFD7 #000000",
                "dialog.body": "bg:#000000 #5FFFD7",
                "dialog shadow": "bg:#171E2B",
                "button": "bg:#000000",
                "text-area": "bg:#000000 #5FFFD7",
                # Label bg and font color
                "primary_label": "bg:#5FFFD7 #262626",
                "secondary_label": "bg:#FFFFFF #262626",
                "success_label": "bg:#5FFFD7 #262626",
                "warning_label": "bg:#FFFF00 #262626",
                "info_label": "bg:#5FD7FF #262626",
                "error_label": "bg:#FF0000 #262626"
            }
        )

        self.assertEqual(style.class_names_and_attrs, reset_style(config_map=adapter, save=False).class_names_and_attrs)

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
