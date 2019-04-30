from os.path import isfile
from hummingbot.cli.settings import (
    EXCHANGES,
    STRATEGIES,
)


# Validators
def is_exchange(value: str) -> bool:
    return value in EXCHANGES


def is_strategy(value: str) -> bool:
    return value in STRATEGIES


def is_path(value: str) -> bool:
    return isfile(value) and value.endswith('.yml')


def is_valid_market_symbol(market: str, value: str) -> bool:
    if symbol_fetcher.ready:
        market_symbols = symbol_fetcher.symbols.get(market, [])
        return value in symbol_fetcher.symbols.get(market) if len(market_symbols) > 0 else True


