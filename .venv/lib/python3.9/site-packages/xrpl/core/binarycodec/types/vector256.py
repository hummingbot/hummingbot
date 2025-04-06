"""Codec for serializing and deserializing vectors of Hash256."""

from __future__ import annotations

from typing import List, Optional, Type

from typing_extensions import Final, Self

from xrpl.core.binarycodec import XRPLBinaryCodecException
from xrpl.core.binarycodec.binary_wrappers.binary_parser import BinaryParser
from xrpl.core.binarycodec.types.hash256 import Hash256
from xrpl.core.binarycodec.types.serialized_type import SerializedType

_HASH_LENGTH_BYTES: Final[int] = 32


class Vector256(SerializedType):
    """Codec for serializing and deserializing vectors of Hash256."""

    def __init__(self: Self, buffer: bytes) -> None:
        """Construct a Vector256."""
        super().__init__(buffer)

    @classmethod
    def from_value(cls: Type[Self], value: List[str]) -> Self:
        """Construct a Vector256 from a list of strings.

        Args:
            value: A list of hashes encoded as hex strings.

        Returns:
            A Vector256 object representing these hashes.

        Raises:
            XRPLBinaryCodecException: If the supplied value is of the wrong type.
        """
        if not isinstance(value, list):
            raise XRPLBinaryCodecException(
                "Invalid type to construct a Vector256: expected list,"
                " received {value.__class__.__name__}."
            )

        byte_list = []
        for string in value:
            byte_list.append(bytes(Hash256.from_value(string)))
        return cls(b"".join(byte_list))

    @classmethod
    def from_parser(
        cls: Type[Self], parser: BinaryParser, length_hint: Optional[int] = None
    ) -> Self:
        """Construct a Vector256 from a BinaryParser.

        Args:
            parser: The parser to construct a Vector256 from.
            length_hint: The number of bytes to consume from the parser.

        Returns:
            A Vector256 object.
        """
        byte_list = []
        num_bytes = length_hint if length_hint is not None else len(parser)
        num_hashes = num_bytes // _HASH_LENGTH_BYTES
        for i in range(num_hashes):
            byte_list.append(bytes(Hash256.from_parser(parser)))
        return cls(b"".join(byte_list))

    def to_json(self: Self) -> List[str]:
        """Return a list of hashes encoded as hex strings.

        Returns:
            The JSON representation of this Vector256.

        Raises:
            XRPLBinaryCodecException: If the number of bytes in the buffer
                                        is not a multiple of the hash length.
        """
        if len(self.buffer) % _HASH_LENGTH_BYTES != 0:
            raise XRPLBinaryCodecException("Invalid bytes for Vector256.")
        hash_list = []
        for i in range(0, len(self.buffer), _HASH_LENGTH_BYTES):
            hash_list.append(self.buffer[i : i + _HASH_LENGTH_BYTES].hex().upper())
        return hash_list
