from os.path import (
    isfile,
    join,
)
from hummingbot.core.utils.symbol_fetcher import SymbolFetcher
from hummingbot.client.settings import (
    EXCHANGES,
    STRATEGIES,
    CONF_FILE_PATH,
)


# Validators
def is_exchange(value: str) -> bool:
    return value in EXCHANGES


def is_strategy(value: str) -> bool:
    return value in STRATEGIES


def is_path(value: str) -> bool:
    return isfile(join(CONF_FILE_PATH, value)) and value.endswith('.yml')


def is_valid_market_symbol(market: str, value: str) -> bool:
    # Since symbol validation and autocomplete are UI optimizations that do not impact bot performances,
    # in case of network issues or slow wifi, this check returns true and does not prevent users from proceeding,
    symbol_fetcher: SymbolFetcher = SymbolFetcher.get_instance()
    if symbol_fetcher.ready:
        market_symbols = symbol_fetcher.symbols.get(market, [])
        return value in symbol_fetcher.symbols.get(market) if len(market_symbols) > 0 else True
    else:
        return True


