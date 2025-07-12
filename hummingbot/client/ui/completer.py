import importlib
import inspect
import os
import re
import sys
from os import listdir
from os.path import exists, isfile, join
from typing import List

from prompt_toolkit.completion import CompleteEvent, Completer, WordCompleter
from prompt_toolkit.document import Document

from hummingbot.client import settings
from hummingbot.client.command.connect_command import OPTIONS as CONNECT_OPTIONS
from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.client.settings import (
    SCRIPT_STRATEGIES_PATH,
    SCRIPT_STRATEGY_CONF_DIR_PATH,
    STRATEGIES,
    STRATEGIES_CONF_DIR_PATH,
    AllConnectorSettings,
)
from hummingbot.client.ui.parser import ThrowingArgumentParser
from hummingbot.core.rate_oracle.rate_oracle import RATE_ORACLE_SOURCES
from hummingbot.core.utils.gateway_config_utils import list_gateway_wallets
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
from hummingbot.strategy.strategy_v2_base import StrategyV2ConfigBase


def file_name_list(path, file_extension):
    if not exists(path):
        return []
    return sorted([f for f in listdir(path) if isfile(join(path, f)) and f.endswith(file_extension)])


class HummingbotCompleter(Completer):
    def __init__(self, hummingbot_application):
        super(HummingbotCompleter, self).__init__()
        self.hummingbot_application = hummingbot_application
        self._path_completer = WordCompleter(file_name_list(str(STRATEGIES_CONF_DIR_PATH), "yml"))
        self._command_completer = WordCompleter(self.parser.commands, ignore_case=True)
        self._exchange_completer = WordCompleter(sorted(AllConnectorSettings.get_connector_settings().keys()), ignore_case=True)
        self._spot_exchange_completer = WordCompleter(sorted(AllConnectorSettings.get_exchange_names()), ignore_case=True)
        self._exchange_amm_completer = WordCompleter(sorted(AllConnectorSettings.get_gateway_amm_connector_names()), ignore_case=True)
        self._exchange_ethereum_completer = WordCompleter(sorted(AllConnectorSettings.get_gateway_ethereum_connector_names()), ignore_case=True)
        self._exchange_clob_completer = WordCompleter(sorted(AllConnectorSettings.get_exchange_names()), ignore_case=True)
        self._exchange_clob_amm_completer = WordCompleter(sorted(AllConnectorSettings.get_exchange_names().union(
            AllConnectorSettings.get_gateway_amm_connector_names())), ignore_case=True)
        self._trading_timeframe_completer = WordCompleter(["infinite", "from_date_to_date", "daily_between_times"], ignore_case=True)
        self._derivative_completer = WordCompleter(AllConnectorSettings.get_derivative_names(), ignore_case=True)
        self._derivative_exchange_completer = WordCompleter(AllConnectorSettings.get_derivative_names(), ignore_case=True)
        self._connect_option_completer = WordCompleter(CONNECT_OPTIONS, ignore_case=True)
        self._export_completer = WordCompleter(["keys", "trades"], ignore_case=True)
        self._balance_completer = WordCompleter(["limit", "paper"], ignore_case=True)
        self._history_completer = WordCompleter(["--days", "--verbose", "--precision"], ignore_case=True)
        self._gateway_completer = WordCompleter(["ping", "list", "config", "token", "wallet", "balance", "allowance", "approve", "pool", "swap", "wrap", "generate-certs", "restart"], ignore_case=True)

        # Initialize gateway wallet chain completer first
        self._gateway_wallet_chain_completer = WordCompleter([
            "ethereum",
            "solana"
        ], ignore_case=True)

        self._gateway_balance_completer = self._gateway_wallet_chain_completer
        self._gateway_config_completer = WordCompleter(hummingbot_application.gateway_config_keys, ignore_case=True)
        self._gateway_wallet_completer = WordCompleter(["list", "add", "remove", "setDefault"], ignore_case=True)
        self._gateway_wallet_action_completer = WordCompleter(["list", "add", "add-hardware", "remove", "setDefault"], ignore_case=True)
        self._gateway_token_action_completer = WordCompleter(["list", "show", "add", "remove"], ignore_case=True)
        self._gateway_pool_action_completer = WordCompleter(["list", "show", "add", "remove"], ignore_case=True)
        self._gateway_pool_type_completer = WordCompleter(["amm", "clmm"], ignore_case=True)
        self._gateway_swap_side_completer = WordCompleter(["BUY", "SELL"], ignore_case=True)
        self._gateway_config_action_completer = WordCompleter(["show", "update"], ignore_case=True)
        # Initialize empty - will be updated dynamically from gateway
        self._gateway_config_namespaces = []
        self._gateway_config_namespace_completer = WordCompleter(self._gateway_config_namespaces, ignore_case=True)
        self._cached_gateway_chains = []
        self._strategy_completer = WordCompleter(STRATEGIES, ignore_case=True)
        self._script_strategy_completer = WordCompleter(file_name_list(str(SCRIPT_STRATEGIES_PATH), "py"))
        self._script_conf_completer = WordCompleter(["--conf"], ignore_case=True)
        self._scripts_config_completer = WordCompleter(file_name_list(str(SCRIPT_STRATEGY_CONF_DIR_PATH), "yml"))
        self._strategy_v2_create_config_completer = self.get_strategies_v2_with_config()
        self._controller_completer = self.get_available_controllers()
        self._rate_oracle_completer = WordCompleter(list(RATE_ORACLE_SOURCES.keys()), ignore_case=True)
        self._mqtt_completer = WordCompleter(["start", "stop", "restart"], ignore_case=True)
        self._gateway_chains = []
        self._list_gateway_wallets_parameters = {"wallets": [], "chain": ""}
        self._cached_gateway_connectors = []  # Cache for dynamically fetched connectors
        self._gateway_token_symbols = []  # Cache for token symbols
        self._all_gateway_wallets = []  # Cache for all gateway wallets
        self._gateway_config_path_options = []  # Dynamic config path options for interactive mode

    def get_strategies_v2_with_config(self):
        file_names = file_name_list(str(SCRIPT_STRATEGIES_PATH), "py")
        strategies_with_config = []

        for script_name in file_names:
            try:
                script_name = script_name.replace(".py", "")
                module = sys.modules.get(f"{settings.SCRIPT_STRATEGIES_MODULE}.{script_name}")
                if module is not None:
                    script_module = importlib.reload(module)
                else:
                    script_module = importlib.import_module(f".{script_name}",
                                                            package=settings.SCRIPT_STRATEGIES_MODULE)
                config_class = next((member for member_name, member in inspect.getmembers(script_module)
                                     if inspect.isclass(member) and member not in [BaseClientModel, StrategyV2ConfigBase] and
                                     (issubclass(member, BaseClientModel) or issubclass(member, StrategyV2ConfigBase))))
                if config_class:
                    strategies_with_config.append(script_name)
            except Exception:
                pass
        return WordCompleter(strategies_with_config, ignore_case=True)

    def get_available_controllers(self):
        controllers_path = settings.CONTROLLERS_PATH  # Ensure this points to the controllers directory
        available_controllers = []

        for root, dirs, files in os.walk(controllers_path):
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    # Extract controller name from file path
                    relative_path = os.path.relpath(os.path.join(root, file), controllers_path)
                    controller_name = os.path.splitext(relative_path)[0].replace(os.path.sep, ".")
                    available_controllers.append(controller_name)

        return WordCompleter(available_controllers, ignore_case=True)

    def set_gateway_chains(self, gateway_chains):
        self._gateway_chains = gateway_chains

    def set_list_gateway_wallets_parameters(self, wallets, chain):
        self._list_gateway_wallets_parameters = {"wallets": wallets, "chain": chain}

    def update_gateway_chains(self, chains: List[str]):
        """Update the cached gateway chains list"""
        self._cached_gateway_chains = sorted(chains) if chains else []

    def update_gateway_config_namespaces(self, namespaces: List[str]):
        """Update the gateway config namespaces list"""
        if namespaces:
            self._gateway_config_namespaces = sorted(namespaces)
            self._gateway_config_namespace_completer = WordCompleter(self._gateway_config_namespaces, ignore_case=True)

    @property
    def prompt_text(self) -> str:
        return self.hummingbot_application.app.prompt_text

    @property
    def parser(self) -> ThrowingArgumentParser:
        return self.hummingbot_application.parser

    def get_subcommand_completer(self, first_word: str) -> Completer:
        subcommands: List[str] = self.parser.subcommands_from(first_word)
        return WordCompleter(subcommands, ignore_case=True)

    @property
    def _trading_pair_completer(self) -> Completer:
        trading_pair_fetcher = TradingPairFetcher.get_instance()
        market = ""
        for exchange in sorted(list(AllConnectorSettings.get_connector_settings().keys()), key=len, reverse=True):
            if exchange in self.prompt_text:
                market = exchange
                break
        trading_pairs = trading_pair_fetcher.trading_pairs.get(market, []) if trading_pair_fetcher.ready and market else []
        return WordCompleter(trading_pairs, ignore_case=True, sentence=True)

    @property
    def _gateway_chain_completer(self):
        return WordCompleter(self._gateway_chains, ignore_case=True)

    @property
    def _gateway_wallet_address_completer(self):
        # Use all cached wallets if available
        if self._all_gateway_wallets:
            wallets = self._all_gateway_wallets
        else:
            wallets = self._list_gateway_wallets_parameters["wallets"]

        chain = self._list_gateway_wallets_parameters["chain"]
        return WordCompleter(list_gateway_wallets(wallets, chain), ignore_case=True)

    def _get_ethereum_spenders_completer(self):
        """Get Ethereum-based spenders (connector/type combinations)"""
        spenders = [
            "uniswap/amm",
            "uniswap/clmm",
            "uniswap/router",
            "0x/router",
        ]
        return WordCompleter(spenders, ignore_case=True)

    def _get_wallet_addresses_for_chain_network(self, chain: str, network: str = None):
        """Get wallet addresses for a specific chain and optionally network"""
        addresses = []
        try:
            # First try using all cached wallets
            if self._all_gateway_wallets:
                addresses = list_gateway_wallets(self._all_gateway_wallets, chain)
            elif self._list_gateway_wallets_parameters.get("chain") == chain:
                wallets = self._list_gateway_wallets_parameters.get("wallets", [])
                addresses = list_gateway_wallets(wallets, chain)
        except Exception:
            pass

        # Remove duplicates
        addresses = list(set(addresses))

        # If no addresses found, provide a helpful placeholder
        if not addresses:
            addresses = ["<Enter wallet address>"]

        return WordCompleter(addresses, ignore_case=True)

    @property
    def _gateway_available_chains_completer(self):
        """Get available chains from gateway configuration"""
        # Use cached chains if available
        if self._cached_gateway_chains:
            return WordCompleter(self._cached_gateway_chains, ignore_case=True)
        else:
            # Provide default chains (same as wallet chain completer)
            return WordCompleter(["ethereum", "solana"], ignore_case=True)

    @property
    def _gateway_available_connectors_completer(self):
        """Get available connectors from gateway configuration"""
        # Simple approach - just provide default connectors
        return WordCompleter(["0x", "uniswap", "jupiter", "meteora", "raydium", "dummy-connector"], ignore_case=True)

    @property
    def _gateway_swap_connectors_completer(self):
        """Get swap connectors with type suffixes from gateway configuration"""
        # Simple static list of swap connectors with types
        connectors = ["0x/router", "uniswap/router", "uniswap/amm", "jupiter/router",
                      "meteora/clmm", "raydium/amm", "raydium/clmm", "dummy/swap"]
        return WordCompleter(connectors, ignore_case=True)

    @property
    def _option_completer(self):
        outer = re.compile(r"\((.+)\)")
        inner_str = outer.search(self.prompt_text).group(1)
        options = inner_str.split("/") if "/" in inner_str else []
        return WordCompleter(options, ignore_case=True)

    @property
    def _config_completer(self):
        config_keys = self.hummingbot_application.configurable_keys()
        return WordCompleter(config_keys, ignore_case=True)

    def _complete_strategies(self, document: Document) -> bool:
        return "strategy" in self.prompt_text and "strategy file" not in self.prompt_text

    def _complete_pmm_script_files(self, document: Document) -> bool:
        return "PMM script file" in self.prompt_text

    def _complete_configs(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("config")

    def _complete_options(self, document: Document) -> bool:
        return "(" in self.prompt_text and ")" in self.prompt_text and "/" in self.prompt_text

    def _complete_exchanges(self, document: Document) -> bool:
        return any(x for x in ("exchange name", "name of exchange", "name of the exchange")
                   if x in self.prompt_text.lower())

    def _complete_derivatives(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return "perpetual" in text_before_cursor or \
               any(x for x in ("derivative connector", "derivative name", "name of derivative", "name of the derivative")
                   if x in self.prompt_text.lower())

    def _complete_connect_options(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("connect ")

    def _complete_exchange_amm_connectors(self, document: Document) -> bool:
        return "(Exchange/AMM)" in self.prompt_text

    def _complete_exchange_clob_connectors(self, document: Document) -> bool:
        return "(Exchange/CLOB)" in self.prompt_text

    def _complete_exchange_clob_amm_connectors(self, document: Document) -> bool:
        return "(Exchange/AMM/CLOB)" in self.prompt_text

    def _complete_spot_exchanges(self, document: Document) -> bool:
        return "spot" in self.prompt_text

    def _complete_trading_timeframe(self, document: Document) -> bool:
        return any(x for x in ("trading timeframe", "execution timeframe")
                   if x in self.prompt_text.lower())

    def _complete_export_options(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return "export" in text_before_cursor

    def _complete_balance_options(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("balance ")

    def _complete_history_arguments(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("history ")

    def _complete_gateway_balance_arguments(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("gateway balance ")

    # Removed _complete_gateway_balance_address and _complete_gateway_balance_network
    # as gateway balance now only takes chain and optional tokens parameters

    def _complete_gateway_allowance_spender(self, document: Document) -> bool:
        """Check if we're completing the spender argument for gateway allowance"""
        text_before_cursor: str = document.text_before_cursor
        if not text_before_cursor.startswith("gateway allowance "):
            return False

        # Count the number of arguments after "gateway allowance"
        cmd_part = text_before_cursor.replace("gateway allowance ", "").strip()

        # If no arguments yet or we're typing the first argument, we're completing the spender
        if not cmd_part:
            return True

        args = cmd_part.split()
        # If we're still typing the first argument (spender)
        return len(args) == 1 and not text_before_cursor.endswith(" ")

    # Removed _complete_gateway_allowance_network and _complete_gateway_allowance_address
    # as gateway allowance now only takes spender and optional tokens parameters

    # Removed _complete_gateway_approve_network
    # as gateway approve now only takes spender and tokens parameters

    def _complete_gateway_wrap_arguments(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("gateway wrap ")

    def _complete_gateway_approve_spender(self, document: Document) -> bool:
        """Check if we're completing the spender argument for gateway approve"""
        text_before_cursor: str = document.text_before_cursor
        if not text_before_cursor.startswith("gateway approve "):
            return False

        # Count the number of arguments after "gateway approve"
        cmd_part = text_before_cursor.replace("gateway approve ", "").strip()

        # If no arguments yet or we're typing the first argument, we're completing the spender
        if not cmd_part:
            return True

        args = cmd_part.split()
        # We're completing the connector if we have 0 complete args or if we're typing the first arg
        return len(args) == 0 or (len(args) == 1 and not text_before_cursor.endswith(" "))

    def _complete_gateway_arguments(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return (text_before_cursor.startswith("gateway ") and
                not text_before_cursor.startswith("gateway config ") and
                not text_before_cursor.startswith("gateway wallet ") and
                not text_before_cursor.startswith("gateway token ") and
                not text_before_cursor.startswith("gateway pool ") and
                text_before_cursor.count(" ") == 1)

    def _complete_gateway_config_arguments(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("gateway config ") and text_before_cursor.count(" ") == 2

    def _complete_gateway_config_namespace(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        # Complete namespace for: gateway config show <namespace> or gateway config update <namespace>
        return ((text_before_cursor.startswith("gateway config show ") and text_before_cursor.count(" ") == 3) or
                (text_before_cursor.startswith("gateway config update ") and text_before_cursor.count(" ") == 3))

    def _complete_gateway_config_paths(self, document: Document) -> bool:
        """Check if we're in a prompt that expects config paths"""
        return self.prompt_text == "Enter configuration path: "

    def _complete_gateway_ping_chain(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("gateway ping ") and text_before_cursor.count(" ") == 2

    # Removed _complete_gateway_ping_network
    # as gateway ping now only takes optional chain parameter

    def _complete_gateway_wallet_arguments(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("gateway wallet ") and text_before_cursor.count(" ") == 2

    def _complete_gateway_wallet_chain_arguments(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return ((text_before_cursor.startswith("gateway wallet add ") and text_before_cursor.count(" ") == 3) or
                (text_before_cursor.startswith("gateway wallet add-hardware ") and text_before_cursor.count(" ") == 3) or
                (text_before_cursor.startswith("gateway wallet remove ") and text_before_cursor.count(" ") == 3) or
                (text_before_cursor.startswith("gateway wallet setDefault ") and text_before_cursor.count(" ") == 3) or
                (text_before_cursor.startswith("gateway wallet list ") and text_before_cursor.count(" ") == 3))

    def _complete_gateway_wallet_remove_address(self, document: Document) -> bool:
        """Check if we're completing the address argument for gateway wallet remove"""
        text_before_cursor: str = document.text_before_cursor
        return (text_before_cursor.startswith("gateway wallet remove ") and
                text_before_cursor.count(" ") >= 4 and
                not text_before_cursor.endswith("  "))  # Not multiple spaces

    def _complete_gateway_wallet_add_hardware_address(self, document: Document) -> bool:
        """Check if we're completing the address argument for gateway wallet add-hardware"""
        text_before_cursor: str = document.text_before_cursor
        return (text_before_cursor.startswith("gateway wallet add-hardware ") and
                text_before_cursor.count(" ") >= 4 and
                not text_before_cursor.endswith("  "))  # Not multiple spaces

    def _complete_gateway_wallet_setdefault_address(self, document: Document) -> bool:
        """Check if we're completing the address argument for gateway wallet setDefault"""
        text_before_cursor: str = document.text_before_cursor
        return (text_before_cursor.startswith("gateway wallet setDefault ") and
                text_before_cursor.count(" ") >= 4 and
                not text_before_cursor.endswith("  "))  # Not multiple spaces

    def _complete_gateway_token_arguments(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("gateway token ") and text_before_cursor.count(" ") == 2

    def _complete_gateway_token_chain_arguments(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        # Complete chain as the first argument after action
        return ((text_before_cursor.startswith("gateway token list ") and text_before_cursor.count(" ") == 3) or
                (text_before_cursor.startswith("gateway token add ") and text_before_cursor.count(" ") == 3) or
                (text_before_cursor.startswith("gateway token remove ") and text_before_cursor.count(" ") == 3) or
                (text_before_cursor.startswith("gateway token show ") and text_before_cursor.count(" ") == 3))

    def _complete_gateway_pool_arguments(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("gateway pool ") and text_before_cursor.count(" ") == 2

    def _complete_gateway_pool_connector(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return ((text_before_cursor.startswith("gateway pool list ") and text_before_cursor.count(" ") == 3) or
                (text_before_cursor.startswith("gateway pool add ") and text_before_cursor.count(" ") == 3) or
                (text_before_cursor.startswith("gateway pool remove ") and text_before_cursor.count(" ") == 3))

    def _complete_gateway_pool_type(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("gateway pool list ") and text_before_cursor.count(" ") == 5

    def _complete_gateway_swap_connector(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("gateway swap ") and text_before_cursor.count(" ") == 2

    def _complete_gateway_swap_side(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        # After "gateway swap <connector> <base-quote>"
        return text_before_cursor.startswith("gateway swap ") and text_before_cursor.count(" ") >= 4

    def _complete_script_strategy_files(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("start --script ") and "--conf" not in text_before_cursor and ".py" not in text_before_cursor

    def _complete_conf_param_script_strategy_config(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("start --script ") and "--conf" not in text_before_cursor

    def _complete_script_strategy_config(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("start --script ") and "--conf" in text_before_cursor

    def _complete_strategy_v2_files_with_config(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("create --script-config ")

    def _complete_controllers_config(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("create --controller-config ")

    def _complete_trading_pairs(self, document: Document) -> bool:
        return "trading pair" in self.prompt_text

    def _complete_paths(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return (("path" in self.prompt_text and "file" in self.prompt_text) or
                "import" in text_before_cursor)

    def _complete_gateway_chain(self, document: Document) -> bool:
        return "Which chain do you want" in self.prompt_text

    def _complete_gateway_wallet_addresses(self, document: Document) -> bool:
        return "Select a gateway wallet" in self.prompt_text

    def _complete_gateway_tokens(self, document: Document) -> bool:
        return "Enter base token" in self.prompt_text or "Enter quote token" in self.prompt_text

    def _complete_command(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return " " not in text_before_cursor and len(self.prompt_text.replace(">>> ", "")) == 0

    def _complete_subcommand(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        index: int = text_before_cursor.index(' ')
        return text_before_cursor[0:index] in self.parser.commands

    def _complete_balance_limit_exchanges(self, document: Document):
        text_before_cursor: str = document.text_before_cursor
        command_args = text_before_cursor.split(" ")
        return len(command_args) == 3 and command_args[0] == "balance" and command_args[1] == "limit"

    def _complete_rate_oracle_source(self, document: Document):
        return all(x in self.prompt_text for x in ("source", "rate oracle"))

    def _complete_mqtt_arguments(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("mqtt ")

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        """
        Get completions for the current scope. This is the defining function for the completer
        :param document:
        :param complete_event:
        """
        if self._complete_script_strategy_files(document):
            for c in self._script_strategy_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_conf_param_script_strategy_config(document):
            for c in self._script_conf_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_script_strategy_config(document):
            for c in self._scripts_config_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_strategy_v2_files_with_config(document):
            for c in self._strategy_v2_create_config_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_controllers_config(document):
            for c in self._controller_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_paths(document):
            for c in self._path_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_strategies(document):
            for c in self._strategy_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_chain(document):
            for c in self._gateway_chain_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_wallet_addresses(document):
            for c in self._gateway_wallet_address_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_tokens(document):
            token_completer = WordCompleter(self._gateway_token_symbols, ignore_case=True)
            for c in token_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_config_paths(document):
            config_path_completer = WordCompleter(self._gateway_config_path_options, ignore_case=True)
            for c in config_path_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_exchange_clob_amm_connectors(document):
            for c in self._exchange_clob_amm_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_exchange_amm_connectors(document):
            if self._complete_spot_exchanges(document):
                for c in self._spot_exchange_completer.get_completions(document, complete_event):
                    yield c
            else:
                for c in self._exchange_amm_completer.get_completions(document, complete_event):
                    yield c

        elif self._complete_exchange_clob_connectors(document):
            if self._complete_spot_exchanges(document):
                for c in self._spot_exchange_completer.get_completions(document, complete_event):
                    yield c
            elif self._complete_derivatives(document):
                for c in self._derivative_exchange_completer.get_completions(document, complete_event):
                    yield c
            else:
                for c in self._exchange_clob_completer.get_completions(document, complete_event):
                    yield c

        elif self._complete_spot_exchanges(document):
            for c in self._spot_exchange_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_trading_timeframe(document):
            for c in self._trading_timeframe_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_connect_options(document):
            for c in self._connect_option_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_export_options(document):
            for c in self._export_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_balance_limit_exchanges(document):
            for c in self._connect_option_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_balance_options(document):
            for c in self._balance_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_history_arguments(document):
            for c in self._history_completer.get_completions(document, complete_event):
                yield c

        # Removed gateway balance network and address completers as they're no longer needed

        elif self._complete_gateway_balance_arguments(document):
            for c in self._gateway_balance_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_allowance_spender(document):
            spender_completer = self._get_ethereum_spenders_completer()
            for c in spender_completer.get_completions(document, complete_event):
                yield c

        # Removed gateway allowance network and address completers as they're no longer needed

        elif self._complete_gateway_approve_spender(document):
            spender_completer = self._get_ethereum_spenders_completer()
            for c in spender_completer.get_completions(document, complete_event):
                yield c

        # Removed gateway approve network completer as it's no longer needed

        elif self._complete_gateway_wrap_arguments(document):
            # Complete chain names for wrap command
            chains_completer = self._get_gateway_chains_completer()
            for c in chains_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_ping_chain(document):
            for c in self._gateway_available_chains_completer.get_completions(document, complete_event):
                yield c

        # Removed gateway ping network completer as it's no longer needed

        elif self._complete_gateway_wallet_remove_address(document) or self._complete_gateway_wallet_add_hardware_address(document) or self._complete_gateway_wallet_setdefault_address(document):
            # Extract chain from the command
            text_before_cursor: str = document.text_before_cursor
            parts = text_before_cursor.split()
            if len(parts) >= 4:
                chain = parts[3]  # gateway wallet remove <chain> ...

                # Try to get wallets directly from gateway
                addresses = []
                try:
                    from hummingbot.client.hummingbot_application import HummingbotApplication
                    app = HummingbotApplication.main_application()
                    if app and hasattr(app, '_gateway_monitor') and app._gateway_monitor:
                        gateway_instance = app._gateway_monitor.client
                        if gateway_instance:
                            # Try cache first
                            if hasattr(gateway_instance, '_wallets_cache') and chain in gateway_instance._wallets_cache:
                                chain_wallets = gateway_instance._wallets_cache[chain]
                                for wallet in chain_wallets:
                                    if isinstance(wallet, dict):
                                        addresses.extend(wallet.get("walletAddresses", []))
                                        addresses.extend(wallet.get("hardwareWalletAddresses", []))
                            # If no cache, use _all_gateway_wallets
                            elif self._all_gateway_wallets:
                                addresses = list_gateway_wallets(self._all_gateway_wallets, chain)
                except Exception:
                    pass

                # Remove duplicates and create completer
                addresses = list(set(addresses)) if addresses else ["<Enter wallet address>"]
                address_completer = WordCompleter(addresses, ignore_case=True)

                for c in address_completer.get_completions(document, complete_event):
                    yield c

        elif self._complete_gateway_wallet_chain_arguments(document):
            for c in self._gateway_available_chains_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_wallet_arguments(document):
            for c in self._gateway_wallet_action_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_token_arguments(document):
            for c in self._gateway_token_action_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_token_chain_arguments(document):
            for c in self._gateway_available_chains_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_pool_arguments(document):
            for c in self._gateway_pool_action_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_pool_connector(document):
            for c in self._gateway_available_connectors_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_pool_type(document):
            for c in self._gateway_pool_type_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_swap_connector(document):
            for c in self._gateway_swap_connectors_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_swap_side(document):
            for c in self._gateway_swap_side_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_arguments(document) and not document.text_before_cursor.startswith("gateway swap "):
            for c in self._gateway_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_config_arguments(document):
            for c in self._gateway_config_action_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_gateway_config_namespace(document):
            # Provide a simple list of namespaces
            if not self._gateway_config_namespaces:
                # Default namespaces based on known chains and connectors
                default_namespaces = [
                    "0x", "ethereum", "ethereum-arbitrum", "ethereum-avalanche", "ethereum-base",
                    "ethereum-bsc", "ethereum-celo", "ethereum-mainnet", "ethereum-optimism",
                    "ethereum-polygon", "ethereum-sepolia", "jupiter", "meteora", "raydium",
                    "server", "solana", "solana-devnet", "solana-mainnet-beta", "uniswap", "dummy-namespace"
                ]
                self.update_gateway_config_namespaces(default_namespaces)

            for c in self._gateway_config_namespace_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_derivatives(document):
            if self._complete_exchanges(document):
                for c in self._derivative_exchange_completer.get_completions(document, complete_event):
                    yield c
            elif "(Exchange/CLOB)" in self.prompt_text:
                for c in self._derivative_completer.get_completions(document, complete_event):
                    yield c
            else:
                for c in self._derivative_completer.get_completions(document, complete_event):
                    yield c

        elif self._complete_exchanges(document):
            for c in self._exchange_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_trading_pairs(document):
            for c in self._trading_pair_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_command(document):
            for c in self._command_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_configs(document):
            for c in self._config_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_options(document):
            for c in self._option_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_rate_oracle_source(document):
            for c in self._rate_oracle_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_mqtt_arguments(document):
            for c in self._mqtt_completer.get_completions(document, complete_event):
                yield c

        else:
            text_before_cursor: str = document.text_before_cursor
            try:
                first_word: str = text_before_cursor[0:text_before_cursor.index(' ')]
            except ValueError:
                return

            # Don't show subcommand help for gateway commands after the sub-command
            if text_before_cursor.startswith("gateway "):
                # Count spaces to determine argument position
                space_count = text_before_cursor.count(" ")
                # For gateway commands, only show help after "gateway" (1 space) or "gateway [subcommand]" (2 spaces)
                # Don't show help for additional arguments
                if space_count > 2:
                    return

            subcommand_completer: Completer = self.get_subcommand_completer(first_word)
            if complete_event.completion_requested or self._complete_subcommand(document):
                for c in subcommand_completer.get_completions(document, complete_event):
                    yield c


def load_completer(hummingbot_application):
    return HummingbotCompleter(hummingbot_application)
