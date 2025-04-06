"""
Class for serializing and deserializing a 64-bit UInt.
See `UInt Fields <https://xrpl.org/serialization.html#uint-fields>`_
"""

from __future__ import annotations

import re
from typing import Optional, Pattern, Type, Union

from typing_extensions import Final, Self

from xrpl.core.binarycodec.binary_wrappers.binary_parser import BinaryParser
from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.uint import UInt

_WIDTH: Final[int] = 8  # 64 / 8

_BASE10_REGEX: Final[Pattern[str]] = re.compile("^[0-9]{1,20}$")
_HEX_REGEX: Final[Pattern[str]] = re.compile("^[a-fA-F0-9]{1,16}$")

_SPECIAL_FIELDS: Final[set[str]] = {
    "MaximumAmount",
    "OutstandingAmount",
    "MPTAmount",
}


class UInt64(UInt):
    """
    Class for serializing and deserializing a 64-bit UInt.
    See `UInt Fields <https://xrpl.org/serialization.html#uint-fields>`_
    """

    def __init__(self: Self, buffer: bytes = bytes(_WIDTH)) -> None:
        """Construct a new UInt64 type from a ``bytes`` value."""
        super().__init__(buffer)

    @classmethod
    def from_parser(
        cls: Type[Self], parser: BinaryParser, _length_hint: Optional[int] = None
    ) -> Self:
        """
        Construct a new UInt64 type from a BinaryParser.

        Args:
            parser: The BinaryParser to construct a UInt64 from.

        Returns:
            The UInt64 constructed from parser.
        """
        return cls(parser.read(_WIDTH))

    @classmethod
    def from_value(
        cls: Type[Self], value: Union[str, int], field_name: str = ""
    ) -> Self:
        """
        Construct a new UInt64 type from a value.

        Args:
            value: The value to construct a UInt64 from.
            field_name: The optional field name (for special handling
                        of base 10 strings).

        Returns:
            The UInt64 constructed from the value.

        Raises:
            XRPLBinaryCodecException: If a UInt64 could not be constructed
                                      from the value.
        """
        if isinstance(value, int):
            if value < 0:
                raise XRPLBinaryCodecException(f"{value} must be an unsigned integer")
            value_bytes = value.to_bytes(_WIDTH, byteorder="big", signed=False)
            return cls(value_bytes)

        if isinstance(value, str):
            if field_name in _SPECIAL_FIELDS and _BASE10_REGEX.fullmatch(value):
                # Convert base 10 string to hex string
                value = hex(int(value))[2:]

            if not _HEX_REGEX.fullmatch(value):
                raise XRPLBinaryCodecException(f"{value} is not a valid hex string")

            value = value.rjust(16, "0")
            value_bytes = bytes.fromhex(value)
            return cls(value_bytes)

        raise XRPLBinaryCodecException(
            f"Cannot construct UInt64 from given value {value}"
        )

    def to_json(self: Self, field_name: str = "") -> str:
        """
        Convert a UInt64 object to JSON (hex or base 10, depending on field_name).

        Args:
            field_name: The optional field name (for special handling
                        of base 10 format).

        Returns:
            The JSON representation of the UInt64 object.
        """
        hex_string = self.buffer.hex().upper()
        if field_name in _SPECIAL_FIELDS:
            return str(int(hex_string, 16))  # Return base 10 string
        return hex_string
