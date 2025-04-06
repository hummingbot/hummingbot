"""Class for serializing/deserializing Dicts of objects."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, Union

from typing_extensions import Final, Self

from xrpl.core.addresscodec import is_valid_xaddress, xaddress_to_classic_address
from xrpl.core.binarycodec.binary_wrappers.binary_parser import BinaryParser
from xrpl.core.binarycodec.definitions import (
    FieldInstance,
    get_field_instance,
    get_ledger_entry_type_code,
    get_ledger_entry_type_name,
    get_transaction_result_code,
    get_transaction_result_name,
    get_transaction_type_code,
    get_transaction_type_name,
)
from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException
from xrpl.core.binarycodec.types.serialized_type import SerializedType

_OBJECT_END_MARKER_BYTE: Final[bytes] = bytes([0xE1])
_OBJECT_END_MARKER: Final[str] = "ObjectEndMarker"
_ST_OBJECT: Final[str] = "STObject"
_DESTINATION: Final[str] = "Destination"
_ACCOUNT: Final[str] = "Account"
_SOURCE_TAG: Final[str] = "SourceTag"
_DEST_TAG: Final[str] = "DestinationTag"

_UNL_MODIFY_TX: Final[str] = "0066"


def _handle_xaddress(field: str, xaddress: str) -> Dict[str, Union[str, int]]:
    """Break down an X-Address into a classic address and a tag.

    Args:
        field: Name of field
        xaddress: X-Address corresponding to the field

    Returns:
        A dictionary representing the classic address and tag.

    Raises:
        XRPLBinaryCodecException: field-tag combo is invalid.
    """
    (classic_address, tag, is_test_network) = xaddress_to_classic_address(xaddress)
    if field == _DESTINATION:
        tag_name = _DEST_TAG
    elif field == _ACCOUNT:
        tag_name = _SOURCE_TAG
    elif tag is not None:
        raise XRPLBinaryCodecException(f"{field} cannot have an associated tag")

    if tag is not None:
        return {field: classic_address, tag_name: tag}
    return {field: classic_address}


def _str_to_enum(field: str, value: str) -> Union[str, int]:
    # all of these fields have enum values that are used for serialization
    # converts the string name to the corresponding enum code
    if field == "TransactionType":
        return get_transaction_type_code(value)
    if field == "TransactionResult":
        return get_transaction_result_code(value)
    if field == "LedgerEntryType":
        return get_ledger_entry_type_code(value)
    return value


def _enum_to_str(field: str, value: int) -> Union[str, int]:
    # reverse of the above function
    if field == "TransactionType":
        return get_transaction_type_name(value)
    if field == "TransactionResult":
        return get_transaction_result_name(value)
    if field == "LedgerEntryType":
        return get_ledger_entry_type_name(value)
    return value


class STObject(SerializedType):
    """Class for serializing/deserializing Dicts of objects."""

    @classmethod
    def from_parser(
        cls: Type[Self],
        parser: BinaryParser,
        _length_hint: Optional[None] = None,
    ) -> Self:
        """
        Construct a STObject from a BinaryParser.

        Args:
            parser: The parser to construct a STObject from.

        Returns:
            The STObject constructed from parser.
        """
        from xrpl.core.binarycodec.binary_wrappers.binary_serializer import (
            BinarySerializer,
        )

        serializer = BinarySerializer()

        while not parser.is_end():
            field = parser.read_field()
            if field.name == _OBJECT_END_MARKER:
                break

            associated_value = parser.read_field_value(field)
            serializer.write_field_and_value(field, associated_value)
            if field.type == _ST_OBJECT:
                serializer.append(_OBJECT_END_MARKER_BYTE)

        return cls(bytes(serializer))

    @classmethod
    def from_value(
        cls: Type[Self], value: Dict[str, Any], only_signing: bool = False
    ) -> Self:
        """
        Create a STObject object from a dictionary.

        Args:
            value: The dictionary to construct a STObject from.
            only_signing: whether only the signing fields should be included.

        Returns:
            The STObject object constructed from value.

        Raises:
            XRPLBinaryCodecException: If the STObject can't be constructed
                from value.
        """
        from xrpl.core.binarycodec.binary_wrappers.binary_serializer import (
            BinarySerializer,
        )

        serializer = BinarySerializer()

        xaddress_decoded = {}
        for k, v in value.items():
            if isinstance(v, str) and is_valid_xaddress(v):
                handled = _handle_xaddress(k, v)
                if (
                    _SOURCE_TAG in handled
                    and handled[_SOURCE_TAG] is not None
                    and _SOURCE_TAG in value
                    and value[_SOURCE_TAG] is not None
                    and handled[_SOURCE_TAG] != value[_SOURCE_TAG]
                ):
                    raise XRPLBinaryCodecException(
                        "Cannot have mismatched Account X-Address and SourceTag"
                    )
                if (
                    _DEST_TAG in handled
                    and handled[_DEST_TAG] is not None
                    and _DEST_TAG in value
                    and value[_DEST_TAG] is not None
                    and handled[_DEST_TAG] != value[_DEST_TAG]
                ):
                    raise XRPLBinaryCodecException(
                        "Cannot have mismatched Destination X-Address and "
                        "DestinationTag"
                    )
                xaddress_decoded.update(handled)
            else:
                xaddress_decoded[k] = _str_to_enum(k, v)

        sorted_keys: List[FieldInstance] = []
        for field_name in xaddress_decoded:
            field_instance = get_field_instance(field_name)
            if (
                field_instance is not None
                and xaddress_decoded[field_instance.name] is not None
                and field_instance.is_serialized
            ):
                sorted_keys.append(field_instance)
        sorted_keys.sort(key=lambda x: x.ordinal)

        if only_signing:
            sorted_keys = list(filter(lambda x: x.is_signing, sorted_keys))

        is_unl_modify = False

        for field in sorted_keys:
            try:
                associated_value = field.associated_type.from_value(
                    xaddress_decoded[field.name]
                )
            except XRPLBinaryCodecException as e:
                # mildly hacky way to get more context in the error
                # provides the field name and not just the type it's expecting
                # keeps the original stack trace
                e.args = (f"Error processing {field.name}: {e.args[0]}",) + e.args[1:]
                raise
            if (
                field.name == "TransactionType"
                and str(associated_value) == _UNL_MODIFY_TX
            ):
                # triggered when the TransactionType field has a value of 'UNLModify'
                is_unl_modify = True
            is_unl_modify_workaround = field.name == "Account" and is_unl_modify
            # true when in the UNLModify pseudotransaction (after the transaction type
            # has been processed) and working with the Account field
            # The Account field must not be a part of the UNLModify pseudotransaction
            # encoding, due to a bug in rippled

            serializer.write_field_and_value(
                field, associated_value, is_unl_modify_workaround
            )
            if field.type == _ST_OBJECT:
                serializer.append(_OBJECT_END_MARKER_BYTE)

        return cls(bytes(serializer))

    def to_json(self: Self) -> Dict[str, Any]:
        """
        Returns the JSON representation of a STObject.

        Returns:
            The JSON representation of a STObject.
        """
        parser = BinaryParser(str(self))
        accumulator = {}

        while not parser.is_end():
            field = parser.read_field()
            if field.name == _OBJECT_END_MARKER:
                break
            json_value = parser.read_field_value(field).to_json()
            accumulator[field.name] = _enum_to_str(field.name, json_value)

        return accumulator
