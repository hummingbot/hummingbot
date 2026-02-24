import unittest
from types import SimpleNamespace

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from hummingbot.client.ui.completer import HummingbotCompleter


class HummingbotCompleterTest(unittest.TestCase):
    def _completer_with_prompt(self, prompt: str) -> HummingbotCompleter:
        completer = HummingbotCompleter.__new__(HummingbotCompleter)
        completer.hummingbot_application = SimpleNamespace(app=SimpleNamespace(prompt_text=prompt))
        return completer

    def test_option_completer_uses_last_parenthesized_options(self):
        prompt = (
            "Should the strategy wait to receive a confirmation for orders cancellation "
            "before creating a new set of orders? "
            "(Not waiting requires enough available balance) (Yes/No) >>> "
        )
        completer = self._completer_with_prompt(prompt)

        completions = [
            completion.text
            for completion in completer._option_completer.get_completions(
                Document(text="n"),
                CompleteEvent(completion_requested=True),
            )
        ]

        self.assertEqual(["No"], completions)
