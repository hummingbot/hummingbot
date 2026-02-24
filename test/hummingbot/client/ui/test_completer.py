import unittest
from types import SimpleNamespace

from prompt_toolkit.document import Document

from hummingbot.client.ui.completer import HummingbotCompleter


class HummingbotCompleterTest(unittest.TestCase):
    def _completer(self) -> HummingbotCompleter:
        completer = HummingbotCompleter.__new__(HummingbotCompleter)
        completer.hummingbot_application = SimpleNamespace(app=SimpleNamespace(prompt_text=">>> "))
        return completer

    def test_start_script_completes_script_names_while_typing_first_argument(self):
        completer = self._completer()

        self.assertTrue(
            completer._complete_script_strategy_files(Document(text="start --script v2_funding_rate_arb"))
        )
        self.assertFalse(
            completer._complete_conf_param_script_strategy_config(Document(text="start --script v2_funding_rate_arb"))
        )

    def test_start_script_suggests_conf_flag_after_script_argument_without_py_extension(self):
        completer = self._completer()

        document = Document(text="start --script v2_funding_rate_arb ")
        self.assertFalse(completer._complete_script_strategy_files(document))
        self.assertTrue(completer._complete_conf_param_script_strategy_config(document))

    def test_start_script_suggests_conf_flag_after_script_argument_with_py_extension(self):
        completer = self._completer()

        document = Document(text="start --script v2_funding_rate_arb.py ")
        self.assertFalse(completer._complete_script_strategy_files(document))
        self.assertTrue(completer._complete_conf_param_script_strategy_config(document))
