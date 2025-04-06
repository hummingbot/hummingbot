"""
Types for encoding and decoding data.
"""

from typing import (
    NewType,
    Union,
)

HexStr = NewType("HexStr", str)
"""
A string that represents a hex encoded value.
"""
Primitives = Union[bytes, int, bool]
"""
A type that represents bytes, int or bool primitive types.
"""
