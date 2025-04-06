"""
Codec for serializing and deserializing a hash field with a width
of 256 bits (32 bytes).
`See Hash Fields <https://xrpl.org/serialization.html#hash-fields>`_
"""

from __future__ import annotations

from typing import Type

from typing_extensions import Self

from xrpl.core.binarycodec.types.hash import Hash


class Hash256(Hash):
    """
    Codec for serializing and deserializing a hash field with a width
    of 256 bits (32 bytes).
    `See Hash Fields <https://xrpl.org/serialization.html#hash-fields>`_
    """

    @classmethod
    def _get_length(cls: Type[Self]) -> int:
        return 32
