"""Class for serializing and deserializing Lists of objects.
See `Array Fields <https://xrpl.org/serialization.html#array-fields>`_
"""

from __future__ import annotations

from typing import Any, List, Optional, Type

from typing_extensions import Final, Self

from xrpl.core.binarycodec.binary_wrappers.binary_parser import BinaryParser
from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.serialized_type import SerializedType
from xrpl.core.binarycodec.types.st_object import STObject

_ARRAY_END_MARKER: Final[bytes] = bytes([0xF1])
_ARRAY_END_MARKER_NAME: Final[str] = "ArrayEndMarker"

_OBJECT_END_MARKER: Final[bytes] = bytes([0xE1])


class STArray(SerializedType):
    """Class for serializing and deserializing Lists of objects.
    See `Array Fields <https://xrpl.org/serialization.html#array-fields>`_
    """

    @classmethod
    def from_parser(
        cls: Type[Self],
        parser: BinaryParser,
        _length_hint: Optional[None] = None,
    ) -> Self:
        """
        Construct a STArray from a BinaryParser.

        Args:
            parser: The parser to construct a STArray from.

        Returns:
            The STArray constructed from parser.
        """
        bytestring = b""

        while not parser.is_end():
            field = parser.read_field()
            if field.name == _ARRAY_END_MARKER_NAME:
                break
            bytestring += bytes(field.header)
            bytestring += bytes(parser.read_field_value(field))
            bytestring += _OBJECT_END_MARKER

        bytestring += _ARRAY_END_MARKER
        return cls(bytestring)

    @classmethod
    def from_value(cls: Type[Self], value: List[Any]) -> Self:
        """
        Create a STArray object from a dictionary.

        Args:
            value: The dictionary to construct a STArray from.

        Returns:
            The STArray object constructed from value.

        Raises:
            XRPLBinaryCodecException: If the provided value isn't a list or contains
                non-dict elements.
        """
        if not isinstance(value, list):
            raise XRPLBinaryCodecException(
                "Invalid type to construct a STArray:"
                " expected list, received {value.__class__.__name__}."
            )

        if len(value) > 0 and not isinstance(value[0], dict):
            raise XRPLBinaryCodecException(
                ("Cannot construct STArray from a list of non-dict" " objects")
            )

        bytestring = b""
        for obj in value:
            transaction = STObject.from_value(obj)
            bytestring += bytes(transaction)
        bytestring += _ARRAY_END_MARKER
        return cls(bytestring)

    def to_json(self: Self) -> List[Any]:
        """
        Returns the JSON representation of a STArray.

        Returns:
            The JSON representation of a STArray.
        """
        result = []
        parser = BinaryParser(str(self))

        while not parser.is_end():
            field = parser.read_field()
            if field.name == _ARRAY_END_MARKER_NAME:
                break

            outer = {}
            outer[field.name] = STObject.from_parser(parser).to_json()
            result.append(outer)
        return result
