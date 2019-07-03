import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class HelpCommand:
    def help(self,  # type: HummingbotApplication
             command: str):
        if command == 'all':
            self._notify(self.parser.format_help())
        else:
            subparsers_actions = [
                action for action in self.parser._actions if isinstance(action, argparse._SubParsersAction)]

            for subparsers_action in subparsers_actions:
                subparser = subparsers_action.choices.get(command)
                self._notify(subparser.format_help())
