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

    config_parser = subparsers.add_parser("config", help="Create a new bot or import an existing configuration")
    config_parser.add_argument("key", nargs="?", default=None, help="Configure a specific variable")
    config_parser.set_defaults(func=hummingbot.config)

    help_parser = subparsers.add_parser("help", help="List the commands and get help on each one")
    help_parser.add_argument("command", nargs="?", default="all", help="Get help for a specific command")
    help_parser.set_defaults(func=hummingbot.help)

    start_parser = subparsers.add_parser("start", help="Start your currently configured bot")
    start_parser.add_argument("--log-level", help="Level of logging")
    start_parser.set_defaults(func=hummingbot.start)

    stop_parser = subparsers.add_parser('stop', help='Stop your currently configured bot')
    stop_parser.set_defaults(func=hummingbot.stop)

    status_parser = subparsers.add_parser("status", help="Get the status of a running bot")
    status_parser.set_defaults(func=hummingbot.status)

    history_parser = subparsers.add_parser("history", help="List your bot\'s past trades and analyze performance")
    history_parser.set_defaults(func=hummingbot.history)

    exit_parser = subparsers.add_parser("exit", help="Exit and cancel all outstanding orders")
    exit_parser.add_argument("-f", "--force", action="store_true", help="Does not cancel outstanding orders",
                             default=False)
    exit_parser.set_defaults(func=hummingbot.exit)

    list_parser = subparsers.add_parser("list", help="List global objects like exchanges and trades")
    list_parser.add_argument("obj", choices=["wallets", "exchanges", "configs", "trades", "encrypted"],
                             help="Type of object to list", nargs="?")
    list_parser.set_defaults(func=hummingbot.list)

    paper_trade_parser = subparsers.add_parser("paper_trade", help="Toggle paper trade mode")
    paper_trade_parser.set_defaults(func=hummingbot.paper_trade)

    export_trades_parser = subparsers.add_parser("export_trades", help="Export your bot's trades to a CSV file")
    export_trades_parser.add_argument("-p", "--path", help="Save csv to specific path")
    export_trades_parser.set_defaults(func=hummingbot.export_trades)

    export_private_key_parser = subparsers.add_parser("export_private_key", help="Export your Ethereum wallet private key")
    export_private_key_parser.set_defaults(func=lambda: safe_ensure_future(hummingbot.export_private_key()))

    get_balance_parser = subparsers.add_parser("get_balance", help="Query your balance in an exchange or wallet")
    get_balance_parser.add_argument("-c", "--currency", help="Specify the currency you are querying balance for")
    get_balance_parser.add_argument("-w", "--wallet", action="store_true", help="Get balance in the current wallet")
    get_balance_parser.add_argument("-e", "--exchange", help="Get balance in a specific exchange")
    get_balance_parser.set_defaults(func=hummingbot.get_balance)

    return parser
