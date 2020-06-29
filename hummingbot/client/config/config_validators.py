from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
from hummingbot.client.settings import (
    EXCHANGES,
    STRATEGIES,
)
from decimal import Decimal
from typing import Optional


# Validators
def validate_exchange(value: str) -> Optional[str]:
    if value not in EXCHANGES:
        return f"Invalid exchange, please choose value from {EXCHANGES}"


def validate_strategy(value: str) -> Optional[str]:
    if value not in STRATEGIES:
        return f"Invalid strategy, please choose value from {STRATEGIES}"


def validate_decimal(value: str, min_value: Decimal = None, max_value: Decimal = None, inclusive=True) -> Optional[str]:
    try:
        decimal_value = Decimal(value)
    except Exception:
        return f"{value} is not in decimal format."
    if inclusive:
        if min_value is not None and max_value is not None:
            if not (Decimal(str(min_value)) <= decimal_value <= Decimal(str(max_value))):
                return f"Value must be between {min_value} and {max_value}."
        elif min_value is not None and not decimal_value >= Decimal(str(min_value)):
            return f"Value cannot be less than {min_value}."
        elif max_value is not None and not decimal_value <= Decimal(str(max_value)):
            return f"Value cannot be more than {max_value}."
    else:
        if min_value is not None and max_value is not None:
            if not (Decimal(str(min_value)) < decimal_value < Decimal(str(max_value))):
                return f"Value must be between {min_value} and {max_value} (exclusive)."
        elif min_value is not None and not decimal_value > Decimal(str(min_value)):
            return f"Value must be more than {min_value}."
        elif max_value is not None and not decimal_value < Decimal(str(max_value)):
            return f"Value must be less than {max_value}."


def validate_market_trading_pair(market: str, value: str) -> Optional[str]:
    # Since trading pair validation and autocomplete are UI optimizations that do not impact bot performances,
    # in case of network issues or slow wifi, this check returns true and does not prevent users from proceeding,
    trading_pair_fetcher: TradingPairFetcher = TradingPairFetcher.get_instance()
    if trading_pair_fetcher.ready:
        trading_pairs = trading_pair_fetcher.trading_pairs.get(market)
        if len(trading_pairs) == 0:
            return None
        elif value not in trading_pairs:
            return f"{value} is not an active market on {market}."


def validate_bool(value: str) -> Optional[str]:
    valid_values = ('true', 'yes', 'y', 'false', 'no', 'n')
    if value.lower() not in valid_values:
        return f"Invalid value, please choose value from {valid_values}"


def validate_int(value: str, min_value: Decimal = None, max_value: Decimal = None, inclusive=True) -> Optional[str]:
    try:
        int_value = int(value)
    except Exception:
        return f"{value} is not in integer format."
    if inclusive:
        if not (int(str(min_value)) <= int_value <= int(str(max_value))):
            return f"Value must be between {min_value} and {max_value}."
        elif min_value is not None and not int_value >= int(str(min_value)):
            return f"Value cannot be less than {min_value}."
        elif max_value is not None and not int_value <= int(str(max_value)):
            return f"Value cannot be more than {max_value}."
    else:
        if min_value is not None and max_value is not None:
            if not (int(str(min_value)) < int_value < int(str(max_value))):
                return f"Value must be between {min_value} and {max_value} (exclusive)."
        elif min_value is not None and not int_value > int(str(min_value)):
            return f"Value must be more than {min_value}."
        elif max_value is not None and not int_value < int(str(max_value)):
            return f"Value must be less than {max_value}."
