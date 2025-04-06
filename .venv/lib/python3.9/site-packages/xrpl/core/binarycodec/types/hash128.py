"""
Codec for serializing and deserializing a hash field with a width
of 128 bits (16 bytes).
`See Hash Fields <https://xrpl.org/serialization.html#hash-fields>`_
"""

from __future__ import annotations

from typing import Optional, Type

from typing_extensions import Self

from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.hash import Hash


class Hash128(Hash):
    """
    Codec for serializing and deserializing a hash field with a width
    of 128 bits (16 bytes).
    `See Hash Fields <https://xrpl.org/serialization.html#hash-fields>`_
    """

    def __init__(self: Self, buffer: Optional[bytes]) -> None:
        """
        Construct a Hash128.

        Args:
            buffer: The byte buffer that will be used to store the serialized
                encoding of this field.
        """
        buffer = (
            buffer
            if buffer is not None and len(buffer) > 0
            else bytes(self._get_length())
        )

        if len(buffer) != self._get_length():
            raise XRPLBinaryCodecException(
                f"Invalid hash length {len(buffer)}. Expected {self._get_length()}"
            )
        super().__init__(buffer)

    def __str__(self: Self) -> str:
        """Returns a hex-encoded string representation of the bytes buffer."""
        hex = self.to_hex()
        if hex == "0" * len(hex):
            return ""
        return hex

    @classmethod
    def _get_length(cls: Type[Self]) -> int:
        return 16
