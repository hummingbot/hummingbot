import asyncio
import unittest

from typing import Awaitable
from prompt_toolkit.document import Document

from hummingbot.client.config.config_helpers import read_system_configs_from_yml
from hummingbot.client.ui.custom_widgets import FormattedTextLexer


class CustomWidgetUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.ev_loop.run_until_complete(read_system_configs_from_yml())

        cls.text_style_tag = {"&cSPECIAL_WORD": "SPECIAL_LABEL"}
        cls.tag_css_style = {"SPECIAL_LABEL": "bg: #FF0000"}

    def setUp(self) -> None:
        super().setUp()
        self.lexer = FormattedTextLexer()

        self.lexer.text_style_tag_map.update(self.text_style_tag)
        self.lexer.html_tag_css_style_map.update(self.tag_css_style)

    @classmethod
    def async_run_with_timeout(cls, coroutine: Awaitable, timeout: float = 1):
        ret = cls.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_get_css_style_text_not_listed(self):
        expected_styling = ""
        self.assertEqual(expected_styling, self.lexer.get_css_style("STYLING NOT FOUND"))

    def test_get_css_style_text_listed(self):
        expected_styling = self.tag_css_style["SPECIAL_LABEL"]
        self.assertEqual(expected_styling, self.lexer.get_css_style("SPECIAL_LABEL"))

    def test_get_line_command_promt(self):
        TEST_PROMPT_TEXT = ">>> SOME_RANDOM_COMMAND AND_ARGUMENTS"
        document = Document(text=TEST_PROMPT_TEXT)
        get_line = self.lexer.lex_document(document)

        expected_fragments = [(self.lexer.get_css_style("primary-label"), TEST_PROMPT_TEXT)]

        line_fragments = get_line(0)
        self.assertEqual(1, len(line_fragments))
        self.assertEqual(expected_fragments, line_fragments)

    def test_get_line_match_found(self):
        TEXT = "SOME RANDOM TEXT WITH &cSPECIAL_WORD"
        document = Document(text=TEXT)
        get_line = self.lexer.lex_document(document)

        expected_fragments = [
            ("", "SOME RANDOM TEXT WITH "),
            (self.lexer.get_css_style("output-pane"), "&c"),
            (self.lexer.get_css_style("SPECIAL_LABEL"), "SPECIAL_WORD"),
        ]

        line_fragments = get_line(0)
        self.assertEqual(3, len(line_fragments))
        self.assertEqual(expected_fragments, line_fragments)

    def test_get_line_no_match_found(self):
        TEXT = "SOME RANDOM TEXT WITHOUT SPECIAL_WORD"
        document = Document(text=TEXT)
        get_line = self.lexer.lex_document(document)

        expected_fragments = [("", TEXT)]

        line_fragments = get_line(0)
        self.assertEqual(1, len(line_fragments))
        self.assertEqual(expected_fragments, line_fragments)

    def test_get_line_index_error(self):
        TEXT = "SOME RANDOM TEXT WITHOUT SPECIAL_WORD"
        document = Document(text=TEXT)
        get_line = self.lexer.lex_document(document)

        expected_fragments = []

        line_fragments = get_line(1)
        self.assertEqual(0, len(line_fragments))
        self.assertEqual(expected_fragments, line_fragments)
