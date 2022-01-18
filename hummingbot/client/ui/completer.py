import re
from typing import List
from prompt_toolkit.completion import (
    Completer,
    WordCompleter,
    CompleteEvent,
)
from prompt_toolkit.document import Document
from os import listdir
from os.path import isfile, join, exists
from hummingbot.client.settings import (
    AllConnectorSettings,
    STRATEGIES,
    CONF_FILE_PATH,
    SCRIPTS_PATH,
    ConnectorType
)
from hummingbot.client.ui.parser import ThrowingArgumentParser
from hummingbot.core.utils.wallet_setup import list_wallets
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
from hummingbot.client.command.connect_command import OPTIONS as CONNECT_OPTIONS
from hummingbot.core.rate_oracle.rate_oracle import RateOracleSource


def file_name_list(path, file_extension):
    if not exists(path):
        return []
    return sorted([f for f in listdir(path) if isfile(join(path, f)) and f.endswith(file_extension)])


SPOT_PROTOCOL_CONNECTOR = {x.name for x in AllConnectorSettings.get_connector_settings().values() if x.type == ConnectorType.Connector}
DERIVATIVE_PROTOCOL_CONNECTOR = {x.name for x in AllConnectorSettings.get_connector_settings().values() if x.type == ConnectorType.Derivative and not x.centralised}


class HummingbotCompleter(Completer):
    def __init__(self, hummingbot_application):
        super(HummingbotCompleter, self).__init__()
        self.hummingbot_application = hummingbot_application
        self._path_completer = WordCompleter(file_name_list(CONF_FILE_PATH, "yml"))
        self._command_completer = WordCompleter(self.parser.commands, ignore_case=True)
        self._exchange_completer = WordCompleter(sorted(AllConnectorSettings.get_connector_settings().keys()), ignore_case=True)
        self._spot_completer = WordCompleter(sorted(AllConnectorSettings.get_exchange_names().union(SPOT_PROTOCOL_CONNECTOR)), ignore_case=True)
        self._spot_exchange_completer = WordCompleter(sorted(AllConnectorSettings.get_exchange_names()), ignore_case=True)
        self._trading_timeframe_completer = WordCompleter(["infinite", "from_date_to_date", "daily_between_times"], ignore_case=True)
        self._derivative_completer = WordCompleter(AllConnectorSettings.get_derivative_names(), ignore_case=True)
        self._derivative_exchange_completer = WordCompleter(AllConnectorSettings.get_derivative_names().difference(DERIVATIVE_PROTOCOL_CONNECTOR), ignore_case=True)
        self._connect_option_completer = WordCompleter(CONNECT_OPTIONS, ignore_case=True)
        self._export_completer = WordCompleter(["keys", "trades"], ignore_case=True)
        self._balance_completer = WordCompleter(["limit", "paper"], ignore_case=True)
        self._history_completer = WordCompleter(["--days", "--verbose", "--precision"], ignore_case=True)
        self._gateway_completer = WordCompleter(["generate_certs", "list-configs", "update"], ignore_case=True)
        self._strategy_completer = WordCompleter(STRATEGIES, ignore_case=True)
        self._py_file_completer = WordCompleter(file_name_list(SCRIPTS_PATH, "py"))
        self._rate_oracle_completer = WordCompleter([r.name for r in RateOracleSource], ignore_case=True)

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
    def _wallet_address_completer(self):
        return WordCompleter(list_wallets(), ignore_case=True)

    @property
    def _option_completer(self):
        outer = re.compile(r"\((.+)\)")
        inner_str = outer.search(self.prompt_text).group(1)
        options = inner_str.split("/") if "/" in inner_str else []
        return WordCompleter(options, ignore_case=True)

    @property
    def _config_completer(self):
        config_keys = self.hummingbot_application.config_able_keys()
        return WordCompleter(config_keys, ignore_case=True)

    def _complete_strategies(self, document: Document) -> bool:
        return "strategy" in self.prompt_text and "strategy file" not in self.prompt_text

    def _complete_script_files(self, document: Document) -> bool:
        return "script file" in self.prompt_text

    def _complete_configs(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return "config" in text_before_cursor

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

    def _complete_spot_connectors(self, document: Document) -> bool:
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

    def _complete_gateway_arguments(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return text_before_cursor.startswith("gateway ")

    def _complete_trading_pairs(self, document: Document) -> bool:
        return "trading pair" in self.prompt_text

    def _complete_paths(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return (("path" in self.prompt_text and "file" in self.prompt_text) or
                "import" in text_before_cursor)

    def _complete_wallet_addresses(self, document: Document) -> bool:
        return "Which wallet" in self.prompt_text

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

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        """
        Get completions for the current scope. This is the defining function for the completer
        :param document:
        :param complete_event:
        """
        if self._complete_script_files(document):
            for c in self._py_file_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_paths(document):
            for c in self._path_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_strategies(document):
            for c in self._strategy_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_wallet_addresses(document):
            for c in self._wallet_address_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_spot_connectors(document):
            if "(Exchange/AMM)" in self.prompt_text:
                for c in self._spot_completer.get_completions(document, complete_event):
                    yield c
            else:
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

        elif self._complete_gateway_arguments(document):
            for c in self._gateway_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_derivatives(document):
            if "(Exchange/AMM)" in self.prompt_text:
                for c in self._derivative_completer.get_completions(document, complete_event):
                    yield c
            else:
                for c in self._derivative_exchange_completer.get_completions(document, complete_event):
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

        else:
            text_before_cursor: str = document.text_before_cursor
            try:
                first_word: str = text_before_cursor[0:text_before_cursor.index(' ')]
            except ValueError:
                return
            subcommand_completer: Completer = self.get_subcommand_completer(first_word)
            if complete_event.completion_requested or self._complete_subcommand(document):
                for c in subcommand_completer.get_completions(document, complete_event):
                    yield c


def load_completer(hummingbot_application):
    return HummingbotCompleter(hummingbot_application)
