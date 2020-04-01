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
from decimal import Decimal


# Validators
def validate_exchange(value: str) -> (bool, str):
    if value in EXCHANGES:
        return True, None
    else:
        return False, f"Invalid exchange, please choose value from {EXCHANGES}"


def validate_strategy(value: str) -> (bool, str):
    if value in STRATEGIES:
        return True, None
    else:
        return False, f"Invalid strategy, please choose value from {STRATEGIES}"


def validate_decimal(value: str, min_value: Decimal = None, max_value: Decimal = None) -> (bool, str):
    try:
        decimal_value = Decimal(value)
        if min_value is not None and max_value is not None:
            if not (Decimal(str(min_value)) <= decimal_value <= Decimal(str(max_value))):
                return False, f"Value must be between {min_value} and {max_value}."
        elif min_value is not None:
            if decimal_value < Decimal(str(min_value)):
                return False, f"Value cannot be less than {min_value}."
        elif max_value is not None:
            if decimal_value > Decimal(str(max_value)):
                return False, f"Value cannot be more than {max_value}."
        return True, None
    except ValueError:
        return False, f"{value} is not in decimal format."


def validate_path(value: str) -> (bool, str):
    if not isfile(join(CONF_FILE_PATH, value)):
        return False, f"{value} is not a valid file."
    elif not value.endswith('.yml'):
        return False, f"File extension must be .yml"
    else:
        return True, None


def is_valid_market_trading_pair(market: str, value: str) -> (bool, str):
    # Since trading pair validation and autocomplete are UI optimizations that do not impact bot performances,
    # in case of network issues or slow wifi, this check returns true and does not prevent users from proceeding,
    trading_pair_fetcher: TradingPairFetcher = TradingPairFetcher.get_instance()
    if trading_pair_fetcher.ready:
        trading_pairs = trading_pair_fetcher.trading_pairs.get(market, [])
        return value in trading_pair_fetcher.trading_pairs.get(market) if len(trading_pairs) > 0 else True
    else:
        return True


def validate_bool(value: str) -> (bool, str):
    valid_values = ('true', 'yes', 'y', 'false', 'no', 'n')
    if value.lower() in valid_values:
        return True, None
    else:
        return False, f"Invalid input, please choose value from {valid_values}"
