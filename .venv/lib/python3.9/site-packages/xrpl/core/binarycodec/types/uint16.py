"""Class for serializing and deserializing a 16-bit UInt.
See `UInt Fields <https://xrpl.org/serialization.html#uint-fields>`_
"""

from __future__ import annotations

from typing import Optional, Type

from typing_extensions import Final, Self

from xrpl.core.binarycodec.binary_wrappers.binary_parser import BinaryParser
from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.uint import UInt

_WIDTH: Final[int] = 2  # 16 / 8


class UInt16(UInt):
    """Class for serializing and deserializing a 16-bit UInt.
    See `UInt Fields <https://xrpl.org/serialization.html#uint-fields>`_
    """

    def __init__(self: Self, buffer: bytes = bytes(_WIDTH)) -> None:
        """Construct a new UInt16 type from a ``bytes`` value."""
        super().__init__(buffer)

    @classmethod
    def from_parser(
        cls: Type[Self], parser: BinaryParser, _length_hint: Optional[int] = None
    ) -> Self:
        """
        Construct a new UInt16 type from a BinaryParser.

        Args:
            parser: The BinaryParser to construct a UInt16 from.

        Returns:
            The UInt16 constructed from parser.
        """
        return cls(parser.read(_WIDTH))

    @classmethod
    def from_value(cls: Type[Self], value: int) -> Self:
        """
        Construct a new UInt16 type from a number.

        Args:
            value: The value to construct a UInt16 from.

        Returns:
            The UInt16 constructed from value.

        Raises:
            XRPLBinaryCodecException: If a UInt16 can't be constructed from value.
        """
        if not isinstance(value, int):
            raise XRPLBinaryCodecException(
                "Invalid type to construct a UInt16: expected int, "
                "received {value.__class__.__name__}."
            )

        if isinstance(value, int):
            value_bytes = (value).to_bytes(_WIDTH, byteorder="big", signed=False)
            return cls(value_bytes)

        raise XRPLBinaryCodecException("Cannot construct UInt16 from given value")
