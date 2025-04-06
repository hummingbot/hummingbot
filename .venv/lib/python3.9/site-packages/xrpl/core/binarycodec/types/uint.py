"""Base class for serializing and deserializing unsigned integers.
See `UInt Fields <https://xrpl.org/serialization.html#uint-fields>`_
"""

from __future__ import annotations

from typing import Union

from typing_extensions import Self

from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.serialized_type import SerializedType


class UInt(SerializedType):
    """Base class for serializing and deserializing unsigned integers.
    See `UInt Fields <https://xrpl.org/serialization.html#uint-fields>`_
    """

    def __init__(self: Self, buffer: bytes) -> None:
        """Construct a new UInt type from a ``bytes`` value."""
        self.buffer = buffer

    @property
    def value(self: Self) -> int:
        """
        Get the value of the UInt represented by `self.buffer`.

        Returns:
            The int value of the UInt.
        """
        return int.from_bytes(self.buffer, byteorder="big", signed=False)

    def __eq__(self: Self, other: object) -> bool:
        """Determine whether two UInt objects are equal."""
        if isinstance(other, int):
            return self.value == other
        if isinstance(other, UInt):
            return self.value == other.value
        raise XRPLBinaryCodecException(f"Cannot compare UInt and {type(other)}")

    def __ne__(self: Self, other: object) -> bool:
        """Determine whether two UInt objects are unequal."""
        if isinstance(other, int):
            return self.value != other
        if isinstance(other, UInt):
            return self.value != other.value
        raise XRPLBinaryCodecException(f"Cannot compare UInt and {type(other)}")

    def __lt__(self: Self, other: object) -> bool:
        """Determine whether one UInt object is less than another."""
        if isinstance(other, int):
            return self.value < other
        if isinstance(other, UInt):
            return self.value < other.value
        raise XRPLBinaryCodecException(f"Cannot compare UInt and {type(other)}")

    def __le__(self: Self, other: object) -> bool:
        """Determine whether one UInt object is less than or equal to another."""
        if isinstance(other, int):
            return self.value <= other
        if isinstance(other, UInt):
            return self.value <= other.value
        raise XRPLBinaryCodecException(f"Cannot compare UInt and {type(other)}")

    def __gt__(self: Self, other: object) -> bool:
        """Determine whether one UInt object is greater than another."""
        if isinstance(other, int):
            return self.value > other
        if isinstance(other, UInt):
            return self.value > other.value
        raise XRPLBinaryCodecException(f"Cannot compare UInt and {type(other)}")

    def __ge__(self: Self, other: object) -> bool:
        """Determine whether one UInt object is greater than or equal to another."""
        if isinstance(other, int):
            return self.value >= other
        if isinstance(other, UInt):
            return self.value >= other.value
        raise XRPLBinaryCodecException(f"Cannot compare UInt and {type(other)}")

    def to_json(self: Self) -> Union[str, int]:
        """
        Convert a UInt object to JSON.

        Returns:
            The JSON representation of the UInt object.
        """
        if isinstance(self.value, int):
            return self.value
        return str(self.value)
