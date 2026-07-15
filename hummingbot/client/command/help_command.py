import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class HelpCommand:
    def help(self,  # type: HummingbotApplication
             command: str):
        cmd_split = command.split()
        if cmd_split[0] == 'all':
            self.notify(self.parser.format_help())
        else:
            parser = self.parser._actions
            last_subparser = None
            for step in cmd_split:
                subparsers_actions = [
                    action for action in parser if isinstance(action, argparse._SubParsersAction)]
                for subparsers_action in subparsers_actions:
                    subparser = subparsers_action.choices.get(step)
                    if subparser:
                        last_subparser = subparser
                        parser = subparser._actions
            # if help command is invalid, show message instead of error
            if last_subparser is None:
                self.notify(f"No help available for '{command}'. Type 'help' to see available commands.")
                return
            self.notify(last_subparser.format_help())
