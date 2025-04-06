"""
Codec for serializing and deserializing blob fields.
See `Blob Fields <https://xrpl.org/serialization.html#blob-fields>`_
"""

from __future__ import annotations

from typing import Type

from typing_extensions import Self

from xrpl.core.binarycodec.binary_wrappers.binary_parser import BinaryParser
from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.serialized_type import SerializedType


class Blob(SerializedType):
    """
    Codec for serializing and deserializing blob fields.
    See `Blob Fields <https://xrpl.org/serialization.html#blob-fields>`_
    """

    def __init__(self: Self, buffer: bytes) -> None:
        """Construct a new Blob type from a ``bytes`` value."""
        super().__init__(buffer)

    @classmethod
    def from_parser(cls: Type[Self], parser: BinaryParser, length_hint: int) -> Self:
        """
        Defines how to read a Blob from a BinaryParser.

        Args:
            parser: The parser to construct a Blob from.
            length_hint: The number of bytes to consume from the parser.

        Returns:
            The Blob constructed from parser.
        """
        return cls(parser.read(length_hint))

    @classmethod
    def from_value(cls: Type[Self], value: str) -> Self:
        """
        Create a Blob object from a hex-string.

        Args:
            value: The hex-encoded string to construct a Blob from.

        Returns:
            The Blob constructed from value.

        Raises:
            XRPLBinaryCodecException: If the Blob can't be constructed from value.
        """
        if not isinstance(value, str):
            raise XRPLBinaryCodecException(
                "Invalid type to construct a Blob: expected str, received "
                f"{value.__class__.__name__}."
            )

        if isinstance(value, str):
            return cls(bytes.fromhex(value))

        raise XRPLBinaryCodecException("Cannot construct Blob from value given")
