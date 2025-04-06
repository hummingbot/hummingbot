"""Base class for XRPL Hash types.
`See Hash Fields <https://xrpl.org/serialization.html#hash-fields>`_
"""

from __future__ import annotations  # Requires Python 3.7+

from abc import ABC, abstractmethod
from typing import Optional, Type

from typing_extensions import Self

from xrpl.core.binarycodec.binary_wrappers.binary_parser import BinaryParser
from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.serialized_type import SerializedType


class Hash(SerializedType, ABC):
    """
    Base class for XRPL Hash types.
    `See Hash Fields <https://xrpl.org/serialization.html#hash-fields>`_
    """

    def __init__(self: Self, buffer: Optional[bytes]) -> None:
        """
        Construct a Hash.

        Args:
            buffer: The byte buffer that will be used to store the serialized
                encoding of this field.
        """
        buffer = buffer if buffer is not None else bytes(self._get_length())

        if len(buffer) != self._get_length():
            raise XRPLBinaryCodecException(
                f"Invalid hash length {len(buffer)}. Expected {self._get_length()}"
            )
        super().__init__(buffer)

    def __str__(self: Self) -> str:
        """Returns a hex-encoded string representation of the bytes buffer."""
        return self.to_hex()

    @classmethod
    def from_value(cls: Type[Self], value: str) -> Self:
        """
        Construct a Hash object from a hex string.

        Args:
            value: The value to construct a Hash from.

        Returns:
            The Hash object constructed from value.

        Raises:
            XRPLBinaryCodecException: If the supplied value is of the wrong type.
        """
        if not isinstance(value, str):
            raise XRPLBinaryCodecException(
                f"Invalid type to construct a {cls.__name__}: expected str,"
                f" received {value.__class__.__name__}."
            )

        return cls(bytes.fromhex(value))

    @classmethod
    def from_parser(
        cls: Type[Self], parser: BinaryParser, length_hint: Optional[int] = None
    ) -> Self:
        """
        Construct a Hash object from an existing BinaryParser.

        Args:
            parser: The parser to construct the Hash object from.
            length_hint: The number of bytes to consume from the parser.

        Returns:
            The Hash object constructed from a parser.
        """
        num_bytes = length_hint if length_hint is not None else cls._get_length()
        return cls(parser.read(num_bytes))

    @classmethod
    @abstractmethod
    def _get_length(cls: Type[Self]) -> int:
        pass
