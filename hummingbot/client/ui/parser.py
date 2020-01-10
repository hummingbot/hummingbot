import argparse
from typing import (
    List,
)

from hummingbot.client.errors import ArgumentParserError
from hummingbot.core.utils.async_utils import safe_ensure_future


class ThrowingArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgumentParserError(message)

    def exit(self, status=0, message=None):
        pass

    def print_help(self, file=None):
        pass

    @property
    def subparser_action(self):
        for action in self._actions:
            if isinstance(action, argparse._SubParsersAction):
                return action

    @property
    def commands(self) -> List[str]:
        return list(self.subparser_action._name_parser_map.keys())

    def subcommands_from(self, top_level_command: str) -> List[str]:
        parser: argparse.ArgumentParser = self.subparser_action._name_parser_map.get(top_level_command)
        subcommands = parser._optionals._option_string_actions.keys()
        filtered = list(filter(lambda sub: sub.startswith("--") and sub != "--help", subcommands))
        return filtered


def load_parser(hummingbot) -> ThrowingArgumentParser:
    parser = ThrowingArgumentParser(prog="", add_help=False)
    subparsers = parser.add_subparsers()

    config_parser = subparsers.add_parser("config", help="Add your personal credentials e.g. exchange API keys")
    config_parser.add_argument("key", nargs="?", default=None, help="Configure a specific variable")
    config_parser.set_defaults(func=hummingbot.config)

    exit_parser = subparsers.add_parser("exit", help="Securely exit the command line")
    exit_parser.add_argument("-f", "--force", action="store_true", help="Does not cancel outstanding orders",
                             default=False)
    exit_parser.set_defaults(func=hummingbot.exit)

    export_private_key_parser = subparsers.add_parser("export_private_key", help="Print your account private key")
    export_private_key_parser.set_defaults(func=lambda: safe_ensure_future(hummingbot.export_private_key()))

    export_trades_parser = subparsers.add_parser("export_trades", help="Export your trades to a csv file")
    export_trades_parser.add_argument("-p", "--path", help="Save csv to specific path")
    export_trades_parser.set_defaults(func=hummingbot.export_trades)

    get_balance_parser = subparsers.add_parser("get_balance", help="Print balance of a certain currency ")
    get_balance_parser.add_argument("-c", "--currency", help="Specify the currency you are querying balance for")
    get_balance_parser.add_argument("-w", "--wallet", action="store_true", help="Get balance in the current wallet")
    get_balance_parser.add_argument("-e", "--exchange", help="Get balance in a specific exchange")
    get_balance_parser.set_defaults(func=hummingbot.get_balance)

    help_parser = subparsers.add_parser("help", help="Print a list of commands")
    help_parser.add_argument("command", nargs="?", default="all", help="Get help for a specific command")
    help_parser.set_defaults(func=hummingbot.help)

    history_parser = subparsers.add_parser("history", help="Get your bot\'s past trades and performance analytics")
    history_parser.set_defaults(func=hummingbot.history)

    list_parser = subparsers.add_parser("list", help="List global objects")
    list_parser.add_argument("obj", choices=["wallets", "exchanges", "configs", "trades", "encrypted"],
                             help="Type of object to list", nargs="?")
    list_parser.set_defaults(func=hummingbot.list)

    paper_trade_parser = subparsers.add_parser("paper_trade", help="Enable / Disable paper trade mode.")
    paper_trade_parser.set_defaults(func=hummingbot.paper_trade)

    start_parser = subparsers.add_parser("start", help="Start market making with Hummingbot")
    start_parser.add_argument("--log-level", help="Level of logging")
    start_parser.set_defaults(func=hummingbot.start)

    status_parser = subparsers.add_parser("status", help="Get current bot status")
    status_parser.set_defaults(func=hummingbot.status)

    stop_parser = subparsers.add_parser('stop', help='Stop the bot\'s active strategy')
    stop_parser.set_defaults(func=hummingbot.stop)

    return parser
