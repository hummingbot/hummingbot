"""Maps and helpers providing serialization-related information about fields."""

import json
import os
from typing import Any, Dict, cast

from xrpl.core.binarycodec.definitions.field_header import FieldHeader
from xrpl.core.binarycodec.definitions.field_info import FieldInfo
from xrpl.core.binarycodec.definitions.field_instance import FieldInstance
from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException


def load_definitions(filename: str = "definitions.json") -> Dict[str, Any]:
    """
    Loads JSON from the definitions file and converts it to a preferred format.
    The definitions file contains information required for the XRP Ledger's
    canonical binary serialization format:
    `Serialization <https://xrpl.org/serialization.html>`_

    Args:
        filename: The name of the definitions file.
            (The definitions file should be drop-in compatible with the one from the
            ripple-binary-codec JavaScript package.)

    Returns:
        A dictionary containing the mappings provided in the definitions file.
    """
    dirname = os.path.dirname(__file__)
    absolute_path = os.path.join(dirname, filename)
    with open(absolute_path) as definitions_file:
        definitions = json.load(definitions_file)
        return {
            "TYPES": definitions["TYPES"],
            # type_name str: type_sort_key int
            "FIELDS": {
                k: v for (k, v) in definitions["FIELDS"]
            },  # convert list of tuples to dict
            # "field_name" str: {
            #   "nth": field_sort_key int,
            #   "isVLEncoded": bool,
            #   "isSerialized": bool,
            #   "isSigningField": bool,
            #   "type": string
            # }
            "LEDGER_ENTRY_TYPES": definitions["LEDGER_ENTRY_TYPES"],
            "TRANSACTION_RESULTS": definitions["TRANSACTION_RESULTS"],
            "TRANSACTION_TYPES": definitions["TRANSACTION_TYPES"],
        }


_DEFINITIONS = load_definitions()
_TRANSACTION_TYPE_CODE_TO_STR_MAP = {
    value: key for (key, value) in _DEFINITIONS["TRANSACTION_TYPES"].items()
}
_TRANSACTION_RESULTS_CODE_TO_STR_MAP = {
    value: key for (key, value) in _DEFINITIONS["TRANSACTION_RESULTS"].items()
}
_LEDGER_ENTRY_TYPES_CODE_TO_STR_MAP = {
    value: key for (key, value) in _DEFINITIONS["LEDGER_ENTRY_TYPES"].items()
}

_TYPE_ORDINAL_MAP = _DEFINITIONS["TYPES"]

_FIELD_INFO_MAP = {}
_FIELD_HEADER_NAME_MAP: Dict[FieldHeader, str] = {}

# Populate _FIELD_INFO_MAP and _FIELD_HEADER_NAME_MAP
try:
    for field in _DEFINITIONS["FIELDS"]:
        field_entry = _DEFINITIONS["FIELDS"][field]
        field_info = FieldInfo(
            field_entry["nth"],
            field_entry["isVLEncoded"],
            field_entry["isSerialized"],
            field_entry["isSigningField"],
            field_entry["type"],
        )
        header = FieldHeader(_TYPE_ORDINAL_MAP[field_entry["type"]], field_entry["nth"])
        _FIELD_INFO_MAP[field] = field_info
        _FIELD_HEADER_NAME_MAP[header] = field
except KeyError as e:
    raise XRPLBinaryCodecException(
        f"Malformed definitions.json file. (Original exception: KeyError: {e})"
    )


def get_field_type_name(field_name: str) -> str:
    """
    Returns the serialization data type for the given field name.
    `Serialization Type List <https://xrpl.org/serialization.html#type-list>`_

    Args:
        field_name: The name of the field to get the serialization data type for.

    Returns:
        The serialization data type for the given field name.
    """
    return _FIELD_INFO_MAP[field_name].type


def get_field_type_code(field_name: str) -> int:
    """
    Returns the type code associated with the given field.
    `Serialization Type Codes <https://xrpl.org/serialization.html#type-codes>`_

    Args:
        field_name: The name of the field get a type code for.

    Returns:
        The type code associated with the given field name.

    Raises:
        XRPLBinaryCodecException: If definitions.json is invalid.
    """
    field_type_name = get_field_type_name(field_name)
    field_type_code = _TYPE_ORDINAL_MAP[field_type_name]
    if not isinstance(field_type_code, int):
        raise XRPLBinaryCodecException(
            "Field type codes in definitions.json must be ints."
        )

    return field_type_code


def get_field_code(field_name: str) -> int:
    """
    Returns the field code associated with the given field.
    `Serialization Field Codes <https://xrpl.org/serialization.html#field-codes>`_

    Args:
        field_name: The name of the field to get a field code for.

    Returns:
        The field code associated with the given field.
    """
    return _FIELD_INFO_MAP[field_name].nth


def get_field_header_from_name(field_name: str) -> FieldHeader:
    """
    Returns a FieldHeader object for a field of the given field name.

    Args:
        field_name: The name of the field to get a FieldHeader for.

    Returns:
        A FieldHeader object for a field of the given field name.
    """
    return FieldHeader(get_field_type_code(field_name), get_field_code(field_name))


def get_field_name_from_header(field_header: FieldHeader) -> str:
    """
    Returns the field name described by the given FieldHeader object.

    Args:
        field_header: The header to get a field name for.

    Returns:
        The name of the field described by the given FieldHeader.
    """
    return _FIELD_HEADER_NAME_MAP[field_header]


def get_field_instance(field_name: str) -> FieldInstance:
    """
    Return a FieldInstance object for the given field name.

    Args:
        field_name: The name of the field to get a FieldInstance for.

    Returns:
        A FieldInstance object for the given field name.
    """
    info = _FIELD_INFO_MAP[field_name]
    field_header = get_field_header_from_name(field_name)
    return FieldInstance(
        info,
        field_name,
        field_header,
    )


def get_transaction_type_code(transaction_type: str) -> int:
    """
    Return an integer representing the given transaction type string in an enum.

    Args:
        transaction_type: The name of the transaction type to get the enum value for.

    Returns:
        An integer representing the given transaction type string in an enum.
    """
    return cast(int, _DEFINITIONS["TRANSACTION_TYPES"][transaction_type])


def get_transaction_type_name(transaction_type: int) -> str:
    """
    Return string representing the given transaction type from the enum.

    Args:
        transaction_type: The enum value of the transaction type.

    Returns:
        The string name of the transaction type.
    """
    return cast(str, _TRANSACTION_TYPE_CODE_TO_STR_MAP[transaction_type])


def get_transaction_result_code(transaction_result_type: str) -> int:
    """
    Return an integer representing the given transaction result string in an enum.

    Args:
        transaction_result_type: The name of the transaction result type to get the
            enum value for.

    Returns:
        An integer representing the given transaction result type string in an enum.
    """
    return cast(int, _DEFINITIONS["TRANSACTION_RESULTS"][transaction_result_type])


def get_transaction_result_name(transaction_result_type: int) -> str:
    """
    Return string representing the given transaction result type from the enum.

    Args:
        transaction_result_type: The enum value of the transaction result type.

    Returns:
        The string name of the transaction result type.
    """
    return cast(str, _TRANSACTION_RESULTS_CODE_TO_STR_MAP[transaction_result_type])


def get_ledger_entry_type_code(ledger_entry_type: str) -> int:
    """
    Return an integer representing the given ledger entry type string in an enum.

    Args:
        ledger_entry_type: The name of the ledger entry type to get the enum value for.

    Returns:
        An integer representing the given ledger entry type string in an enum.
    """
    return cast(int, _DEFINITIONS["LEDGER_ENTRY_TYPES"][ledger_entry_type])


def get_ledger_entry_type_name(ledger_entry_type: int) -> str:
    """
    Return string representing the given ledger entry type from the enum.

    Args:
        ledger_entry_type: The enum value of the ledger entry type.

    Returns:
        The string name of the ledger entry type.
    """
    return cast(str, _LEDGER_ENTRY_TYPES_CODE_TO_STR_MAP[ledger_entry_type])
