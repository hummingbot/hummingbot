import unittest

from prompt_toolkit.styles import Style
from hummingbot.client.ui.style import load_style, hex_to_ansi


class StyleTest(unittest.TestCase):

    class ConfigVar():
        value = None

        def __init__(self, value):
            self.value = value

    def test_load_style(self):
        global_config_map = {}
        global_config_map["top-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["bottom-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["output-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["input-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["logs-pane"] = self.ConfigVar("#FAFAFA")
        global_config_map["terminal-primary"] = self.ConfigVar("#FCFCFC")

        style = Style.from_dict({"output-field": "bg:#FAFAFA #FCFCFC",
                                 "input-field": "bg:#FAFAFA #FFFFFF",
                                 "log-field": "bg:#FAFAFA #FFFFFF",
                                 "header": "bg:#FAFAFA #AAAAAA",
                                 "footer": "bg:#FAFAFA #AAAAAA",
                                 "search": "bg:#000000 #93C36D",
                                 "search.current": "bg:#000000 #1CD085",
                                 "primary": "#FCFCFC",
                                 "warning": "#93C36D",
                                 "error": "#F5634A"})

        self.assertEqual(style.class_names_and_attrs, load_style(global_config_map).class_names_and_attrs)

    def test_hex_to_ansi(self):
        self.assertEqual("ansiblack", hex_to_ansi("000000"))
        self.assertEqual("ansired", hex_to_ansi("FF0000"))
        self.assertEqual("ansigreen", hex_to_ansi("00FF00"))
        self.assertEqual("ansiyellow", hex_to_ansi("FFFF00"))
        self.assertEqual("ansiblue", hex_to_ansi("0000FF"))
        self.assertEqual("ansimagenta", hex_to_ansi("FF00FF"))
        self.assertEqual("ansicyan", hex_to_ansi("00FFFF"))
        self.assertEqual("ansigray", hex_to_ansi("F0F0F0"))

        self.assertEqual("ansiyellow", hex_to_ansi("FFFF00"))
        self.assertEqual("ansiyellow", hex_to_ansi("FFAA00"))
        self.assertEqual("ansiyellow", hex_to_ansi("FFFF00"))
        self.assertEqual("ansired", hex_to_ansi("FF1100"))

        self.assertEqual("ansiyellow", hex_to_ansi("ffff00"))
        self.assertEqual("ansiyellow", hex_to_ansi("ffaa00"))
        self.assertEqual("ansiyellow", hex_to_ansi("ffff00"))
        self.assertEqual("ansired", hex_to_ansi("ff1100"))
