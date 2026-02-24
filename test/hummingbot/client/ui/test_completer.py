import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from prompt_toolkit.document import Document

# Importing HummingbotApplication first avoids parser/completer circular import at module load time.
from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401
from hummingbot.client.ui.completer import HummingbotCompleter
from hummingbot.client.ui.parser import load_parser


class HummingbotCompleterTest(unittest.TestCase):
    @staticmethod
    def _completer(prompt_text: str = ">>> ") -> HummingbotCompleter:
        completer = HummingbotCompleter.__new__(HummingbotCompleter)
        completer.hummingbot_application = SimpleNamespace(app=SimpleNamespace(prompt_text=prompt_text))
        return completer

    def test_complete_derivatives_does_not_trigger_from_perpetual_text_in_v2_command(self):
        completer = self._completer()

        document = Document(text="start --v2 conf_simple_perpetual_pmm_1.yml")

        self.assertTrue(completer._complete_v2_config_files(document))
        self.assertFalse(completer._complete_derivatives(document))

    def test_complete_derivatives_triggers_for_derivative_prompt(self):
        completer = self._completer(prompt_text="Select derivative connector >>> ")

        self.assertTrue(completer._complete_derivatives(Document(text="")))

    def test_start_command_parser_only_exposes_v2_option(self):
        parser = load_parser(MagicMock(), {})
        start_options = parser.subcommands_from("start")

        self.assertIn("--v2", start_options)
        self.assertNotIn("--script", start_options)
        self.assertNotIn("--conf", start_options)
