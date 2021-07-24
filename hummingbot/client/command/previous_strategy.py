import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class PreviousCommand:
    def previous_statrategy(
        self,  # type: HummingbotApplication
        option: str,
    ):
        if option == "all":
            self._notify(self.parser.format_help())
        else:
            subparsers_actions = [
                action for action in self.parser._actions if isinstance(action, argparse._SubParsersAction)
            ]

            for subparsers_action in subparsers_actions:
                subparser = subparsers_action.choices.get(option)
                self._notify(subparser.format_help())
