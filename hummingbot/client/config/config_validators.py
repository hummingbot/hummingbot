from os.path import (
    isfile,
    join,
)
from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
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


def is_valid_percent(value: str) -> bool:
    try:
        return 0 <= float(value) < 1
    except ValueError:
        return False


def is_valid_expiration(value: str) -> bool:
    try:
        return float(value) >= 130.0
    except Exception:
        return False


def is_path(value: str) -> bool:
    return isfile(join(CONF_FILE_PATH, value)) and value.endswith('.yml')


def is_valid_market_trading_pair(market: str, value: str) -> bool:
    # Since trading pair validation and autocomplete are UI optimizations that do not impact bot performances,
    # in case of network issues or slow wifi, this check returns true and does not prevent users from proceeding,
    trading_pair_fetcher: TradingPairFetcher = TradingPairFetcher.get_instance()
    if trading_pair_fetcher.ready:
        trading_pairs = trading_pair_fetcher.trading_pairs.get(market, [])
        return value in trading_pair_fetcher.trading_pairs.get(market) if len(trading_pairs) > 0 else True
    else:
        return True


def is_valid_bool(value: str) -> bool:
    return value.lower() in ('true', 'yes', 'y', 'false', 'no', 'n')

