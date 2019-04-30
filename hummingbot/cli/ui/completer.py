import asyncio
from typing import (
    List,
    Dict,
)
from prompt_toolkit.completion import Completer, WordCompleter, PathCompleter, CompleteEvent
from prompt_toolkit.document import Document

from hummingbot.cli.settings import EXCHANGES, STRATEGIES
from hummingbot.cli.ui.parser import ThrowingArgumentParser
from hummingbot.cli.utils.symbol_fetcher import fetch_all
from hummingbot.cli.utils.wallet_setup import list_wallets
from hummingbot.cli.config.in_memory_config_map import load_required_configs


class HummingbotCompleter(Completer):
    def __init__(self, hummingbot_application):
        super(HummingbotCompleter, self).__init__()
        self.hummingbot_application = hummingbot_application
        self._symbols: Dict[str, List[str]] = {}

        # static completers
        self._path_completer = PathCompleter()
        self._command_completer = WordCompleter(self.parser.commands, ignore_case=True)
        self._exchange_completer = WordCompleter(EXCHANGES, ignore_case=True)
        self._strategy_completer = WordCompleter(STRATEGIES, ignore_case=True)

        asyncio.ensure_future(self._fetch_symbols())

    async def _fetch_symbols(self):
        self._symbols: Dict[str, List[str]] = await fetch_all()

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
    def _symbol_completer(self) -> Completer:
        market = None
        for exchange in EXCHANGES:
            if exchange in self.prompt_text:
                market = exchange
                break
        return WordCompleter(self._symbols.get(market) or [], ignore_case=True)

    @property
    def _wallet_address_completer(self):
        return WordCompleter(list_wallets(), ignore_case=True)

    @property
    def _config_completer(self):
        return WordCompleter(load_required_configs(), ignore_case=True)

    def _complete_strategies(self, document: Document) -> bool:
        return "strategy" in self.prompt_text

    def _complete_configs(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return "config" in text_before_cursor

    def _complete_exchanges(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return "-e" in text_before_cursor or \
               "--exchange" in text_before_cursor or \
               "exchange" in self.prompt_text

    def _complete_symbols(self, document: Document) -> bool:
        return "symbol" in self.prompt_text

    def _complete_paths(self, document: Document) -> bool:
        return "path" in self.prompt_text and "file" in self.prompt_text

    def _complete_wallet_addresses(self, document: Document) -> bool:
        return "Which wallet" in self.prompt_text

    def _complete_command(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        return " " not in text_before_cursor and len(self.prompt_text.replace(">>> ", "")) == 0

    def _complete_subcommand(self, document: Document) -> bool:
        text_before_cursor: str = document.text_before_cursor
        index: int = text_before_cursor.index(' ')
        return text_before_cursor[0:index] in self.parser.commands

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        """
        Get completions for the current scope. This is the defining function for the completer
        :param document:
        :param complete_event:
        """
        if self._complete_paths(document):
            for c in self._path_completer.get_completions(document, complete_event):
                yield c

        if self._complete_strategies(document):
            for c in self._strategy_completer.get_completions(document, complete_event):
                yield c

        if self._complete_wallet_addresses(document):
            for c in self._wallet_address_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_exchanges(document):
            for c in self._exchange_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_symbols(document):
            for c in self._symbol_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_command(document):
            for c in self._command_completer.get_completions(document, complete_event):
                yield c

        elif self._complete_configs(document):
            for c in self._config_completer.get_completions(document, complete_event):
                yield c

        else:
            text_before_cursor: str = document.text_before_cursor
            first_word: str = text_before_cursor[0:text_before_cursor.index(' ')]
            subcommand_completer: Completer = self.get_subcommand_completer(first_word)
            if complete_event.completion_requested or self._complete_subcommand(document):
                for c in subcommand_completer.get_completions(document, complete_event):
                    yield c


def load_completer(hummingbot_application):
    return HummingbotCompleter(hummingbot_application)




