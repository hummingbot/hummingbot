"""Codec for serializing and deserializing PathSet fields.
See `PathSet Fields <https://xrpl.org/serialization.html#pathset-fields>`_
"""

from __future__ import annotations

from typing import Dict, List, Optional, Type, cast

from typing_extensions import Final, Self

from xrpl.core.binarycodec.binary_wrappers.binary_parser import BinaryParser
from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.account_id import AccountID
from xrpl.core.binarycodec.types.currency import Currency
from xrpl.core.binarycodec.types.serialized_type import SerializedType

# Constant for masking types of a PathStep
_TYPE_ACCOUNT: Final[int] = 0x01
_TYPE_CURRENCY: Final[int] = 0x10
_TYPE_ISSUER: Final[int] = 0x20

# Constants for separating Paths in a PathSet
_PATHSET_END_BYTE: Final[int] = 0x00
_PATH_SEPARATOR_BYTE: Final[int] = 0xFF


def _is_path_step(value: Dict[str, str]) -> bool:
    """Helper function to determine if a dictionary represents a valid path step."""
    return "issuer" in value or "account" in value or "currency" in value


def _is_path_set(value: List[List[Dict[str, str]]]) -> bool:
    """Helper function to determine if a list represents a valid path set."""
    return len(value) == 0 or len(value[0]) == 0 or _is_path_step(value[0][0])


class PathStep(SerializedType):
    """Serialize and deserialize a single step in a Path."""

    @classmethod
    def from_value(cls: Type[Self], value: Dict[str, str]) -> Self:
        """
        Construct a PathStep object from a dictionary.

        Args:
            value: The dictionary to construct a PathStep object from.

        Returns:
            The PathStep constructed from value.

        Raises:
            XRPLBinaryCodecException: If the supplied value is of the wrong type.
        """
        if not isinstance(value, dict):
            raise XRPLBinaryCodecException(
                "Invalid type to construct a PathStep: expected dict,"
                f" received {value.__class__.__name__}."
            )

        data_type = 0x00
        buffer = b""
        if "account" in value:
            account_id = AccountID.from_value(value["account"])
            buffer += bytes(account_id)
            data_type |= _TYPE_ACCOUNT
        if "currency" in value:
            currency = Currency.from_value(value["currency"])
            buffer += bytes(currency)
            data_type |= _TYPE_CURRENCY
        if "issuer" in value:
            issuer = AccountID.from_value(value["issuer"])
            buffer += bytes(issuer)
            data_type |= _TYPE_ISSUER

        return cls(bytes([data_type]) + buffer)

    @classmethod
    def from_parser(
        cls: Type[Self], parser: BinaryParser, _length_hint: Optional[None] = None
    ) -> Self:
        """
        Construct a PathStep object from an existing BinaryParser.

        Args:
            parser: The parser to construct a PathStep from.

        Returns:
            The PathStep constructed from parser.
        """
        data_type = parser.read_uint8()
        buffer = b""

        if data_type & _TYPE_ACCOUNT:
            account_id = parser.read(AccountID.LENGTH)
            buffer += account_id
        if data_type & _TYPE_CURRENCY:
            currency = parser.read(Currency.LENGTH)
            buffer += currency
        if data_type & _TYPE_ISSUER:
            issuer = parser.read(AccountID.LENGTH)
            buffer += issuer

        return cls(bytes([data_type]) + buffer)

    def to_json(self: Self) -> Dict[str, str]:
        """
        Returns the JSON representation of a PathStep.

        Returns:
            The JSON representation of a PathStep.
        """
        parser = BinaryParser(str(self))
        data_type = parser.read_uint8()
        json = {}

        if data_type & _TYPE_ACCOUNT:
            account_id = AccountID.from_parser(parser).to_json()
            json["account"] = account_id
        if data_type & _TYPE_CURRENCY:
            currency = Currency.from_parser(parser).to_json()
            json["currency"] = currency
        if data_type & _TYPE_ISSUER:
            issuer = AccountID.from_parser(parser).to_json()
            json["issuer"] = issuer

        return json

    @property
    def type(self: Self) -> int:
        """Get a number representing the type of this PathStep.

        Returns:
            a number to be bitwise and-ed with TYPE_ constants to describe the types in
            the PathStep.
        """
        return self.buffer[0]


class Path(SerializedType):
    """Class for serializing/deserializing Paths."""

    @classmethod
    def from_value(cls: Type[Self], value: List[Dict[str, str]]) -> Self:
        """
        Construct a Path from an array of dictionaries describing PathSteps.

        Args:
            value: The array to construct a Path object from.

        Returns:
            The Path constructed from value.

        Raises:
            XRPLBinaryCodecException: If the supplied value is of the wrong type.
        """
        if not isinstance(value, list):
            raise XRPLBinaryCodecException(
                "Invalid type to construct a Path: expected list, "
                f"received {value.__class__.__name__}."
            )

        buffer: bytes = b""
        for PathStep_dict in value:
            pathstep = PathStep.from_value(PathStep_dict)
            buffer += bytes(pathstep)
        return cls(buffer)

    @classmethod
    def from_parser(
        cls: Type[Self], parser: BinaryParser, _length_hint: Optional[None] = None
    ) -> Self:
        """
        Construct a Path object from an existing BinaryParser.

        Args:
            parser: The parser to construct a Path from.

        Returns:
            The Path constructed from parser.
        """
        buffer: List[bytes] = []
        while not parser.is_end():
            pathstep = PathStep.from_parser(parser)
            buffer.append(bytes(pathstep))

            if parser.peek() == cast(bytes, _PATHSET_END_BYTE) or parser.peek() == cast(
                bytes, _PATH_SEPARATOR_BYTE
            ):
                break
        return cls(b"".join(buffer))

    def to_json(self: Self) -> List[Dict[str, str]]:
        """
        Returns the JSON representation of a Path.

        Returns:
            The JSON representation of a Path.
        """
        json = []
        path_parser = BinaryParser(str(self))

        while not path_parser.is_end():
            pathstep = PathStep.from_parser(path_parser)
            json.append(pathstep.to_json())

        return json


class PathSet(SerializedType):
    """Codec for serializing and deserializing PathSet fields.
    See `PathSet Fields <https://xrpl.org/serialization.html#pathset-fields>`_
    """

    @classmethod
    def from_value(cls: Type[Self], value: List[List[Dict[str, str]]]) -> Self:
        """
        Construct a PathSet from a List of Lists representing paths.

        Args:
            value: The List to construct a PathSet object from.

        Returns:
            The PathSet constructed from value.

        Raises:
            XRPLBinaryCodecException: If the PathSet representation is invalid.
        """
        if not isinstance(value, list):
            raise XRPLBinaryCodecException(
                "Invalid type to construct a PathSet: expected list,"
                f" received {value.__class__.__name__}."
            )

        if _is_path_set(value):
            buffer: List[bytes] = []
            for path_dict in value:
                path = Path.from_value(path_dict)
                buffer.append(bytes(path))
                buffer.append(bytes([_PATH_SEPARATOR_BYTE]))

            buffer[-1] = bytes([_PATHSET_END_BYTE])
            return cls(b"".join(buffer))

        raise XRPLBinaryCodecException("Cannot construct PathSet from given value")

    @classmethod
    def from_parser(
        cls: Type[Self], parser: BinaryParser, _length_hint: Optional[None] = None
    ) -> Self:
        """
        Construct a PathSet object from an existing BinaryParser.

        Args:
            parser: The parser to construct a PathSet from.

        Returns:
            The PathSet constructed from parser.
        """
        buffer: List[bytes] = []
        while not parser.is_end():
            path = Path.from_parser(parser)
            buffer.append(bytes(path))
            buffer.append(parser.read(1))

            if buffer[-1][0] == _PATHSET_END_BYTE:
                break
        return cls(b"".join(buffer))

    def to_json(self: Self) -> List[List[Dict[str, str]]]:
        """
        Returns the JSON representation of a PathSet.

        Returns:
            The JSON representation of a PathSet.
        """
        json = []
        pathset_parser = BinaryParser(str(self))

        while not pathset_parser.is_end():
            path = Path.from_parser(pathset_parser)
            json.append(path.to_json())
            pathset_parser.skip(1)

        return json
