import argparse
from typing import TYPE_CHECKING, Any, List

from hummingbot.client.command.connect_command import OPTIONS as CONNECT_OPTIONS
from hummingbot.exceptions import ArgumentParserError

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


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
        if parser is None:
            return []
        subcommands = parser._optionals._option_string_actions.keys()
        filtered = list(filter(lambda sub: sub.startswith("--"), subcommands))
        return filtered


def load_parser(hummingbot: "HummingbotApplication", command_tabs) -> [ThrowingArgumentParser, Any]:
    parser = ThrowingArgumentParser(prog="", add_help=False)
    subparsers = parser.add_subparsers()

    connect_parser = subparsers.add_parser("connect", help="List available exchanges and add API keys to them")
    connect_parser.add_argument("option", nargs="?", choices=CONNECT_OPTIONS, help="Name of the exchange that you want to connect")
    connect_parser.set_defaults(func=hummingbot.connect)

    create_parser = subparsers.add_parser("create", help="Create a new bot")
    create_parser.add_argument("--script-config", dest="script_to_config", nargs="?", default=None, help="Name of the v2 strategy")
    create_parser.add_argument("--controller-config", dest="controller_name", nargs="?", default=None, help="Name of the controller")
    create_parser.set_defaults(func=hummingbot.create)

    import_parser = subparsers.add_parser("import", help="Import an existing bot by loading the configuration file")
    import_parser.add_argument("file_name", nargs="?", default=None, help="Name of the configuration file")
    import_parser.set_defaults(func=hummingbot.import_command)

    help_parser = subparsers.add_parser("help", help="List available commands")
    help_parser.add_argument("command", nargs="?", default="all", help="Enter ")
    help_parser.set_defaults(func=hummingbot.help)

    balance_parser = subparsers.add_parser("balance", help="Display your asset balances across all connected exchanges")
    balance_parser.add_argument("option", nargs="?", choices=["limit", "paper"], default=None,
                                help="Option for balance configuration")
    balance_parser.add_argument("args", nargs="*")
    balance_parser.set_defaults(func=hummingbot.balance)

    config_parser = subparsers.add_parser("config", help="Display the current bot's configuration")
    config_parser.add_argument("key", nargs="?", default=None, help="Name of the parameter you want to change")
    config_parser.add_argument("value", nargs="?", default=None, help="New value for the parameter")
    config_parser.set_defaults(func=hummingbot.config)

    start_parser = subparsers.add_parser("start", help="Start the current bot")
    # start_parser.add_argument("--log-level", help="Level of logging")
    start_parser.add_argument("--script", type=str, dest="script", help="Script strategy file name")
    start_parser.add_argument("--conf", type=str, dest="conf", help="Script config file name")

    start_parser.set_defaults(func=hummingbot.start)

    stop_parser = subparsers.add_parser('stop', help="Stop the current bot")
    stop_parser.set_defaults(func=hummingbot.stop)

    status_parser = subparsers.add_parser("status", help="Get the market status of the current bot")
    status_parser.add_argument("--live", default=False, action="store_true", dest="live", help="Show status updates")
    status_parser.set_defaults(func=hummingbot.status)

    history_parser = subparsers.add_parser("history", help="See the past performance of the current bot")
    history_parser.add_argument("-d", "--days", type=float, default=0, dest="days",
                                help="How many days in the past (can be decimal value)")
    history_parser.add_argument("-v", "--verbose", action="store_true", default=False,
                                dest="verbose", help="List all trades")
    history_parser.add_argument("-p", "--precision", default=None, type=int,
                                dest="precision", help="Level of precions for values displayed")
    history_parser.set_defaults(func=hummingbot.history)

    gateway_parser = subparsers.add_parser("gateway", help="Helper comands for Gateway server.")
    gateway_subparsers = gateway_parser.add_subparsers()

    gateway_balance_parser = gateway_subparsers.add_parser("balance", help="Display your asset balances and allowances across all connected gateway connectors")
    gateway_balance_parser.add_argument("connector_chain_network", nargs="?", default=None, help="Name of connector_chain_network balance and allowance you want to fetch")
    gateway_balance_parser.set_defaults(func=hummingbot.gateway_balance)

    gateway_config_parser = gateway_subparsers.add_parser("config", help="View or update gateway configuration")
    gateway_config_parser.add_argument("key", nargs="?", default=None, help="Name of the parameter you want to view/change")
    gateway_config_parser.add_argument("value", nargs="?", default=None, help="New value for the parameter")
    gateway_config_parser.set_defaults(func=hummingbot.gateway_config)

    gateway_connect_parser = gateway_subparsers.add_parser("connect", help="Create/view connection info for gateway connector")
    gateway_connect_parser.add_argument("connector", nargs="?", default=None, help="Name of connector you want to create a profile for")
    gateway_connect_parser.set_defaults(func=hummingbot.gateway_connect)

    gateway_connector_tokens_parser = gateway_subparsers.add_parser("connector-tokens", help="Report token balances for gateway connectors")
    gateway_connector_tokens_parser.add_argument("connector_chain_network", nargs="?", default=None, help="Name of connector_chain_network you want to edit reported tokens for")
    gateway_connector_tokens_parser.add_argument("new_tokens", nargs="?", default=None, help="Report balance of these tokens - separate multiple tokens with commas (,)")
    gateway_connector_tokens_parser.set_defaults(func=hummingbot.gateway_connector_tokens)

    gateway_approve_tokens_parser = gateway_subparsers.add_parser("approve-tokens", help="Approve tokens for gateway connectors")
    gateway_approve_tokens_parser.add_argument("connector_chain_network", nargs="?", default=None, help="Name of connector you want to approve tokens for")
    gateway_approve_tokens_parser.add_argument("tokens", nargs="?", default=None, help="Approve these tokens")
    gateway_approve_tokens_parser.set_defaults(func=hummingbot.gateway_approve_tokens)

    gateway_cert_parser = gateway_subparsers.add_parser("generate-certs", help="Create ssl certifcate for gateway")
    gateway_cert_parser.set_defaults(func=hummingbot.generate_certs)

    gateway_list_parser = gateway_subparsers.add_parser("list", help="List gateway connectors and chains and tiers")
    gateway_list_parser.set_defaults(func=hummingbot.gateway_list)

    gateway_test_parser = gateway_subparsers.add_parser("test-connection", help="Ping gateway api server")
    gateway_test_parser.set_defaults(func=hummingbot.test_connection)

    exit_parser = subparsers.add_parser("exit", help="Exit and cancel all outstanding orders")
    exit_parser.add_argument("-f", "--force", action="store_true", help="Force exit without canceling outstanding orders",
                             default=False)
    exit_parser.set_defaults(func=hummingbot.exit)

    export_parser = subparsers.add_parser("export", help="Export secure information")
    export_parser.add_argument("option", nargs="?", choices=("keys", "trades"), help="Export choices")
    export_parser.set_defaults(func=hummingbot.export)

    ticker_parser = subparsers.add_parser("ticker", help="Show market ticker of current order book")
    ticker_parser.add_argument("--live", default=False, action="store_true", dest="live", help="Show ticker updates")
    ticker_parser.add_argument("--exchange", type=str, dest="exchange", help="The exchange of the market")
    ticker_parser.add_argument("--market", type=str, dest="market", help="The market (trading pair) of the order book")
    ticker_parser.set_defaults(func=hummingbot.ticker)

    pmm_script_parser = subparsers.add_parser("pmm_script", help="Send command to running PMM script instance")
    pmm_script_parser.add_argument("cmd", nargs="?", default=None, help="Command")
    pmm_script_parser.add_argument("args", nargs="*", default=None, help="Arguments")
    pmm_script_parser.set_defaults(func=hummingbot.pmm_script_command)

    previous_strategy_parser = subparsers.add_parser("previous", help="Imports the last strategy used")
    previous_strategy_parser.add_argument("option", nargs="?", choices=["Yes,No"], default=None)
    previous_strategy_parser.set_defaults(func=hummingbot.previous_strategy)

    mqtt_parser = subparsers.add_parser("mqtt", help="Manage MQTT Bridge to Message brokers")
    mqtt_subparsers = mqtt_parser.add_subparsers()
    mqtt_start_parser = mqtt_subparsers.add_parser("start", help="Start the MQTT Bridge")
    mqtt_start_parser.add_argument(
        "-t",
        "--timeout",
        default=30.0,
        type=float,
        dest="timeout",
        help="Bridge connection timeout"
    )
    mqtt_start_parser.set_defaults(func=hummingbot.mqtt_start)
    mqtt_stop_parser = mqtt_subparsers.add_parser("stop", help="Stop the MQTT Bridge")
    mqtt_stop_parser.set_defaults(func=hummingbot.mqtt_stop)
    mqtt_restart_parser = mqtt_subparsers.add_parser("restart", help="Restart the MQTT Bridge")
    mqtt_restart_parser.add_argument(
        "-t",
        "--timeout",
        default=30.0,
        type=float,
        dest="timeout",
        help="Bridge connection timeout"
    )
    mqtt_restart_parser.set_defaults(func=hummingbot.mqtt_restart)

    # add shortcuts so they appear in command help
    shortcuts = hummingbot.client_config_map.command_shortcuts
    for shortcut in shortcuts:
        help_str = shortcut.help
        command = shortcut.command
        shortcut_parser = subparsers.add_parser(command, help=help_str)
        args = shortcut.arguments
        for i in range(len(args)):
            shortcut_parser.add_argument(f'${i+1}', help=args[i])

    rate_parser = subparsers.add_parser('rate', help="Show rate of a given trading pair")
    rate_parser.add_argument("-p", "--pair", default=None,
                             dest="pair", help="The market trading pair for which you want to get a rate.")
    rate_parser.add_argument("-t", "--token", default=None,
                             dest="token", help="The token who's value you want to get.")
    rate_parser.set_defaults(func=hummingbot.rate)

    for name, command_tab in command_tabs.items():
        o_parser = subparsers.add_parser(name, help=command_tab.tab_class.get_command_help_message())
        for arg_name, arg_properties in command_tab.tab_class.get_command_arguments().items():
            o_parser.add_argument(arg_name, **arg_properties)
        o_parser.add_argument("-c", "--close", default=False, action="store_true", dest="close",
                              help=f"To close the {name} tab.")

    return parser
