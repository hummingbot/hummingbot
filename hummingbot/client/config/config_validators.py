"""
hummingbot.client.config.config_var defines ConfigVar. One of its parameters is a validator, a function that takes a
string and determines whether it is valid input. This file contains many validator functions that are used by various
hummingbot ConfigVars.
"""

import re
import time
from datetime import datetime
from decimal import Decimal
from typing import Optional


def validate_exchange(value: str) -> Optional[str]:
    """
    Restrict valid exchanges to the exchange file names
    """
    from hummingbot.client.settings import AllConnectorSettings
    if value not in AllConnectorSettings.get_exchange_names():
        return f"Invalid exchange, please choose value from {AllConnectorSettings.get_exchange_names()}"


def validate_derivative(value: str) -> Optional[str]:
    """
    restrict valid derivatives to the derivative file names
    """
    from hummingbot.client.settings import AllConnectorSettings
    if value not in AllConnectorSettings.get_derivative_names():
        return f"Invalid derivative, please choose value from {AllConnectorSettings.get_derivative_names()}"


def validate_connector(value: str) -> Optional[str]:
    """
    Restrict valid derivatives to the connector file names
    """
    from hummingbot.client.settings import AllConnectorSettings
    if (value not in AllConnectorSettings.get_connector_settings()
            and value not in AllConnectorSettings.paper_trade_connectors_names):
        return f"Invalid connector, please choose value from {AllConnectorSettings.get_connector_settings().keys()}"


def validate_strategy(value: str) -> Optional[str]:
    """
    Restrict valid derivatives to the strategy file names
    """
    from hummingbot.client.settings import STRATEGIES
    if value not in STRATEGIES:
        return f"Invalid strategy, please choose value from {STRATEGIES}"


def validate_decimal(value: str, min_value: Decimal = None, max_value: Decimal = None, inclusive=True) -> Optional[str]:
    """
    Parse a decimal value from a string. This value can also be clamped.
    """
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
    """
    Since trading pair validation and autocomplete are UI optimizations that do not impact bot performances,
    in case of network issues or slow wifi, this check returns true and does not prevent users from proceeding,
    """
    from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
    trading_pair_fetcher: TradingPairFetcher = TradingPairFetcher.get_instance()
    if trading_pair_fetcher.ready:
        trading_pairs = trading_pair_fetcher.trading_pairs.get(market, [])
        if len(trading_pairs) == 0:
            return None
        elif value not in trading_pairs:
            return f"{value} is not an active market on {market}."


def validate_bool(value: str) -> Optional[str]:
    """
    Permissively interpret a string as a boolean
    """
    valid_values = ('true', 'yes', 'y', 'false', 'no', 'n')
    if value.lower() not in valid_values:
        return f"Invalid value, please choose value from {valid_values}"


def validate_int(value: str, min_value: int = None, max_value: int = None, inclusive=True) -> Optional[str]:
    """
    Parse an int value from a string. This value can also be clamped.
    """
    try:
        int_value = int(value)
    except Exception:
        return f"{value} is not in integer format."
    if inclusive:
        if min_value is not None and max_value is not None:
            if not (min_value <= int_value <= max_value):
                return f"Value must be between {min_value} and {max_value}."
        elif min_value is not None and not int_value >= min_value:
            return f"Value cannot be less than {min_value}."
        elif max_value is not None and not int_value <= max_value:
            return f"Value cannot be more than {max_value}."
    else:
        if min_value is not None and max_value is not None:
            if not (min_value < int_value < max_value):
                return f"Value must be between {min_value} and {max_value} (exclusive)."
        elif min_value is not None and not int_value > min_value:
            return f"Value must be more than {min_value}."
        elif max_value is not None and not int_value < max_value:
            return f"Value must be less than {max_value}."


def validate_float(value: str, min_value: float = None, max_value: float = None, inclusive=True) -> Optional[str]:
    """
    Parse an float value from a string. This value can also be clamped.
    """
    try:
        float_value = float(value)
    except Exception:
        return f"{value} is not in integer format."
    if inclusive:
        if min_value is not None and max_value is not None:
            if not (min_value <= float_value <= max_value):
                return f"Value must be between {min_value} and {max_value}."
        elif min_value is not None and not float_value >= min_value:
            return f"Value cannot be less than {min_value}."
        elif max_value is not None and not float_value <= max_value:
            return f"Value cannot be more than {max_value}."
    else:
        if min_value is not None and max_value is not None:
            if not (min_value < float_value < max_value):
                return f"Value must be between {min_value} and {max_value} (exclusive)."
        elif min_value is not None and not float_value > min_value:
            return f"Value must be more than {min_value}."
        elif max_value is not None and not float_value < max_value:
            return f"Value must be less than {max_value}."


def validate_datetime_iso_string(value: str) -> Optional[str]:
    try:
        datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return "Incorrect date time format (expected is YYYY-MM-DD HH:MM:SS)"


def validate_time_iso_string(value: str) -> Optional[str]:
    try:
        time.strptime(value, '%H:%M:%S')
    except ValueError:
        return "Incorrect time format (expected is HH:MM:SS)"


def validate_with_regex(value: str, pattern: str, error_message: str) -> Optional[str]:
    """
    Validate a string using a regex pattern.
    """
    if not re.match(pattern, value):
        return error_message
