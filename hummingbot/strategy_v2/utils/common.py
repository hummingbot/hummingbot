import hashlib
import random
import time
from enum import Enum
from typing import List, Type, TypeVar

import base58


def generate_unique_id():
    timestamp = time.time()
    unique_component = random.randint(0, 99999)
    raw_id = f"{timestamp}-{unique_component}"
    hashed_id = hashlib.sha256(raw_id.encode()).digest()
    return base58.b58encode(hashed_id).decode()


E = TypeVar('E', bound=Enum)


def parse_enum_value(enum_class: Type[E], value, field_name: str = "field") -> E:
    """
    Parse enum from string name or return as-is if already correct type.

    Args:
        enum_class: The enum class to parse into
        value: The value to parse (string name or enum instance)
        field_name: Name of the field for error messages

    Returns:
        The enum value

    Raises:
        ValueError: If the string doesn't match any enum name

    Example:
        >>> from hummingbot.core.data_type.common import TradeType
        >>> parse_enum_value(TradeType, 'BUY', 'side')
        <TradeType.BUY: 1>
    """
    if isinstance(value, str):
        try:
            return enum_class[value.upper()]
        except KeyError:
            valid_names = [e.name for e in enum_class]
            raise ValueError(f"Invalid {field_name}: '{value}'. Expected one of: {valid_names}")
    return value


def parse_comma_separated_list(value, field_name: str = "field") -> List[float]:
    """
    Parse a comma-separated string, scalar number, or list into a List[float].

    Handles values coming from YAML configs where a single value is deserialized
    as a scalar (int/float) rather than a list.

    Args:
        value: The value to parse (str, int, float, list, or None)
        field_name: Name of the field for error messages

    Returns:
        A list of floats, or an empty list if value is None or empty string.

    Example:
        >>> parse_comma_separated_list("0.01,0.02")
        [0.01, 0.02]
        >>> parse_comma_separated_list(0.01)
        [0.01]
    """
    if value is None:
        return []
    if isinstance(value, str):
        if value == "":
            return []
        return [float(x.strip()) for x in value.split(',')]
    if isinstance(value, (int, float)):
        return [float(value)]
    return value
