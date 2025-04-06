"""Codec for serializing and deserializing a hash field with a width
of 160 bits (20 bytes).
`See Hash Fields <https://xrpl.org/serialization.html#hash-fields>`_
"""

from __future__ import annotations

from typing import Type

from typing_extensions import Self

from xrpl.core.binarycodec.types.hash import Hash


class Hash160(Hash):
    """
    Codec for serializing and deserializing a hash field with a width
    of 160 bits (20 bytes).
    `See Hash Fields <https://xrpl.org/serialization.html#hash-fields>`_
    """

    @classmethod
    def _get_length(cls: Type[Self]) -> int:
        return 20
