"""Collection of public constants for XRPL."""

import re
from decimal import Context
from enum import Enum
from typing import Pattern

from typing_extensions import Final


class CryptoAlgorithm(str, Enum):
    """Represents the supported cryptography algorithms."""

    ED25519 = "ed25519"
    SECP256K1 = "secp256k1"


class XRPLException(Exception):
    """Base Exception for XRPL library."""

    pass


SPECIAL_CHARS_CURRENCY_CODE = re.escape("?!@#$%^&*(){}[]<>|")
ISO_CURRENCY_REGEX: Final[Pattern[str]] = re.compile(
    "[A-Za-z0-9" + SPECIAL_CHARS_CURRENCY_CODE + "]{3}"
)
"""
Matches ISO currencies like "USD" or "EUR" in the format allowed by XRPL.
Check the docs for more information:
https://xrpl.org/currency-formats.html#standard-currency-codes

:meta private:
"""

HEX_REGEX: Final[Pattern[str]] = re.compile(r"^[0-9A-Fa-f]+$")

HEX_CURRENCY_REGEX: Final[Pattern[str]] = re.compile("[A-F0-9]{40}")
"""
Matches hex-encoded currencies in the format allowed by XRPL.

:meta private:
"""

# Constants for validating amounts.
MIN_IOU_EXPONENT: Final[int] = -96
"""
:meta private:
"""
MAX_IOU_EXPONENT: Final[int] = 80
"""
:meta private:
"""
MAX_IOU_PRECISION: Final[int] = 16
"""
:meta private:
"""
MIN_IOU_MANTISSA: Final[int] = 10**15
"""
:meta private:
"""
MAX_IOU_MANTISSA: Final[int] = 10**16 - 1
"""
:meta private:
"""

# Configure Decimal
IOU_DECIMAL_CONTEXT: Final[Context] = Context(
    prec=MAX_IOU_PRECISION, Emax=MAX_IOU_EXPONENT, Emin=MIN_IOU_EXPONENT
)
"""
Decimal context for working with IOUs.
:meta private:
"""


DROPS_DECIMAL_CONTEXT: Final[Context] = Context(prec=18, Emin=0, Emax=18)
"""
Decimal context for working with drops.
:meta private:
"""
