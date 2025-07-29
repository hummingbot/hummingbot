import argparse
from typing import TYPE_CHECKING, List

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


def load_parser(hummingbot: "HummingbotApplication", command_tabs) -> ThrowingArgumentParser:
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

    gateway_parser = subparsers.add_parser("gateway", help="Helper commands for Gateway server.")
    gateway_parser.set_defaults(func=hummingbot.gateway)
    gateway_subparsers = gateway_parser.add_subparsers()

    gateway_allowance_parser = gateway_subparsers.add_parser("allowance", help="Check token allowances for ethereum connectors")
    gateway_allowance_parser.add_argument("connector", nargs="?", default=None, help="Ethereum connector name/type (e.g., uniswap/amm)")
    gateway_allowance_parser.set_defaults(func=hummingbot.gateway_allowance)

    gateway_approve_parser = gateway_subparsers.add_parser("approve", help="Approve token for use with ethereum connectors")
    gateway_approve_parser.add_argument("connector", nargs="?", default=None, help="Connector name/type (e.g., jupiter/router)")
    gateway_approve_parser.add_argument("token", nargs="?", default=None, help="Token symbol to approve (e.g., WETH)")
    gateway_approve_parser.set_defaults(func=hummingbot.gateway_approve)

    gateway_balance_parser = gateway_subparsers.add_parser("balance", help="Check token balances")
    gateway_balance_parser.add_argument("chain", nargs="?", default=None, help="Chain name (e.g., ethereum, solana)")
    gateway_balance_parser.add_argument("tokens", nargs="?", default=None, help="Comma-separated list of tokens to check (optional)")
    gateway_balance_parser.set_defaults(func=hummingbot.gateway_balance)

    gateway_config_parser = gateway_subparsers.add_parser("config", help="Show or update configuration")
    gateway_config_parser.add_argument("namespace", nargs="?", default=None, help="Namespace (e.g., ethereum-mainnet, uniswap)")
    gateway_config_parser.add_argument("action", nargs="?", default=None, help="Action to perform (update)")
    gateway_config_parser.add_argument("args", nargs="*", help="Additional arguments: <path> <value> for direct update")
    gateway_config_parser.set_defaults(func=hummingbot.gateway_config)

    gateway_connect_parser = gateway_subparsers.add_parser("connect", help="Add a wallet for a chain")
    gateway_connect_parser.add_argument("chain", nargs="?", default=None, help="Blockchain chain (e.g., ethereum, solana)")
    gateway_connect_parser.set_defaults(func=hummingbot.gateway_connect)

    gateway_cert_parser = gateway_subparsers.add_parser("generate-certs", help="Create SSL certificate")
    gateway_cert_parser.set_defaults(func=hummingbot.generate_certs)

    gateway_list_parser = gateway_subparsers.add_parser("list", help="List available connectors")
    gateway_list_parser.set_defaults(func=hummingbot.gateway_list)

    gateway_lp_parser = gateway_subparsers.add_parser("lp", help="Manage liquidity positions")
    gateway_lp_parser.add_argument("connector", nargs="?", type=str, help="Connector name/type (e.g., raydium/amm)")
    gateway_lp_parser.add_argument("action", nargs="?", type=str, choices=["add-liquidity", "remove-liquidity", "position-info", "collect-fees"], help="LP action to perform")
    gateway_lp_parser.set_defaults(func=hummingbot.gateway_lp)

    gateway_ping_parser = gateway_subparsers.add_parser("ping", help="Test node and chain/network status")
    gateway_ping_parser.add_argument("chain", nargs="?", default=None, help="Specific chain to test (optional)")
    gateway_ping_parser.set_defaults(func=hummingbot.gateway_ping)

    gateway_pool_parser = gateway_subparsers.add_parser("pool", help="View or update pool information")
    gateway_pool_parser.add_argument("connector", nargs="?", default=None, help="Connector name/type (e.g., uniswap/amm)")
    gateway_pool_parser.add_argument("trading_pair", nargs="?", default=None, help="Trading pair (e.g., ETH-USDC)")
    gateway_pool_parser.add_argument("action", nargs="?", default=None, help="Action to perform (update)")
    gateway_pool_parser.add_argument("args", nargs="*", help="Additional arguments: <address> for direct pool update")
    gateway_pool_parser.set_defaults(func=hummingbot.gateway_pool)

    gateway_swap_parser = gateway_subparsers.add_parser(
        "swap",
        help="Swap tokens")
    gateway_swap_parser.add_argument("connector", nargs="?", default=None,
                                     help="Connector name/type (e.g., jupiter/router)")
    gateway_swap_parser.add_argument("args", nargs="*",
                                     help="Arguments: [base-quote] [side] [amount]. "
                                          "Interactive mode if not all provided. "
                                          "Example: gateway swap uniswap ETH-USDC BUY 0.1")
    gateway_swap_parser.set_defaults(func=hummingbot.gateway_swap)

    gateway_token_parser = gateway_subparsers.add_parser("token", help="View or update token information")
    gateway_token_parser.add_argument("symbol_or_address", nargs="?", default=None, help="Token symbol or address")
    gateway_token_parser.add_argument("action", nargs="?", default=None, help="Action to perform (update)")
    gateway_token_parser.set_defaults(func=hummingbot.gateway_token)

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

    mqtt_parser = subparsers.add_parser("mqtt", help="Manage the MQTT broker bridge")
    mqtt_subparsers = mqtt_parser.add_subparsers()
    mqtt_start_parser = mqtt_subparsers.add_parser("start", help="Start the MQTT broker bridge")
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
