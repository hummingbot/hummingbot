"""Codec for serializing and deserializing bridge fields."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Type, Union

from typing_extensions import Self

from xrpl.core.binarycodec.binary_wrappers.binary_parser import BinaryParser
from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.account_id import AccountID
from xrpl.core.binarycodec.types.issue import Issue
from xrpl.core.binarycodec.types.serialized_type import SerializedType

_TYPE_ORDER: List[Tuple[str, Type[SerializedType]]] = [
    ("LockingChainDoor", AccountID),
    ("LockingChainIssue", Issue),
    ("IssuingChainDoor", AccountID),
    ("IssuingChainIssue", Issue),
]

_TYPE_KEYS = {type[0] for type in _TYPE_ORDER}


class XChainBridge(SerializedType):
    """Codec for serializing and deserializing bridge fields."""

    def __init__(self: Self, buffer: bytes) -> None:
        """Construct a XChainBridge from given bytes."""
        super().__init__(buffer)

    @classmethod
    def from_value(cls: Type[Self], value: Union[str, Dict[str, str]]) -> Self:
        """
        Construct a XChainBridge object from a dictionary representation of a bridge.

        Args:
            value: The dictionary to construct a XChainBridge object from.

        Returns:
            A XChainBridge object constructed from value.

        Raises:
            XRPLBinaryCodecException: If the XChainBridge representation is invalid.
        """
        if isinstance(value, dict) and set(value.keys()) == _TYPE_KEYS:
            buffer = b""
            for name, object_type in _TYPE_ORDER:
                obj = object_type.from_value(value[name])
                if object_type == AccountID:
                    buffer += bytes.fromhex("14")  # AccountID length
                buffer += bytes(obj)
            return cls(buffer)

        raise XRPLBinaryCodecException(
            "Invalid type to construct a XChainBridge: expected dict,"
            f" received {value.__class__.__name__}."
        )

    @classmethod
    def from_parser(
        cls: Type[Self], parser: BinaryParser, length_hint: Optional[int] = None
    ) -> Self:
        """
        Construct a XChainBridge object from an existing BinaryParser.

        Args:
            parser: The parser to construct the XChainBridge object from.
            length_hint: The number of bytes to consume from the parser.

        Returns:
            The XChainBridge object constructed from a parser.
        """
        buffer = b""

        for _, object_type in _TYPE_ORDER:
            if object_type == AccountID:
                # skip the `14` byte and add it by hand
                parser.skip(1)
                buffer += bytes.fromhex("14")
            obj = object_type.from_parser(parser, length_hint)
            buffer += bytes(obj)

        return cls(buffer)

    def to_json(self: Self) -> Union[str, Dict[Any, Any]]:
        """
        Returns the JSON representation of a bridge.

        Returns:
            The JSON representation of a XChainBridge.
        """
        parser = BinaryParser(str(self))
        return_json = {}
        for name, object_type in _TYPE_ORDER:
            if object_type == AccountID:
                parser.skip(1)
            obj = object_type.from_parser(parser, None)
            return_json[name] = obj.to_json()
        return return_json
