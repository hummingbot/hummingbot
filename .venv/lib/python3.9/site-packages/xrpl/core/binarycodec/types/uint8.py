"""
Class for serializing and deserializing an 8-bit UInt.
See `UInt Fields <https://xrpl.org/serialization.html#uint-fields>`_
"""

from __future__ import annotations

from typing import Optional, Type

from typing_extensions import Final, Self

from xrpl.core.binarycodec.binary_wrappers.binary_parser import BinaryParser
from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.uint import UInt

_WIDTH: Final[int] = 1  # 8 / 8


class UInt8(UInt):
    """
    Class for serializing and deserializing an 8-bit UInt.
    See `UInt Fields <https://xrpl.org/serialization.html#uint-fields>`_
    """

    def __init__(self: Self, buffer: bytes = bytes(_WIDTH)) -> None:
        """Construct a new UInt8 type from a ``bytes`` value."""
        super().__init__(buffer)

    @classmethod
    def from_parser(
        cls: Type[Self], parser: BinaryParser, _length_hint: Optional[int] = None
    ) -> Self:
        """
        Construct a new UInt8 type from a BinaryParser.

        Args:
            parser: The parser to construct a UInt8 from.

        Returns:
            A new UInt8.
        """
        return cls(parser.read(_WIDTH))

    @classmethod
    def from_value(cls: Type[Self], value: int) -> Self:
        """
        Construct a new UInt8 type from a number.

        Args:
            value: The value to construct a UInt8 from.

        Returns:
            A new UInt8.

        Raises:
            XRPLBinaryCodecException: If a UInt8 cannot be constructed.
        """
        if not isinstance(value, int):
            raise XRPLBinaryCodecException(
                "Invalid type to construct a UInt8: expected int, "
                f"received {value.__class__.__name__}."
            )

        if isinstance(value, int):
            value_bytes = (value).to_bytes(_WIDTH, byteorder="big", signed=False)
            return cls(value_bytes)

        raise XRPLBinaryCodecException("Cannot construct UInt8 from given value")
