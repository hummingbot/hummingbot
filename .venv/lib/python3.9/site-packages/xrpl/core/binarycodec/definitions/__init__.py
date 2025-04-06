"""Handles the XRPL type and definition specifics."""

from xrpl.core.binarycodec.definitions.definitions import (
    get_field_header_from_name,
    get_field_instance,
    get_field_name_from_header,
    get_ledger_entry_type_code,
    get_ledger_entry_type_name,
    get_transaction_result_code,
    get_transaction_result_name,
    get_transaction_type_code,
    get_transaction_type_name,
    load_definitions,
)
from xrpl.core.binarycodec.definitions.field_header import FieldHeader
from xrpl.core.binarycodec.definitions.field_info import FieldInfo
from xrpl.core.binarycodec.definitions.field_instance import FieldInstance

__all__ = [
    "FieldHeader",
    "FieldInfo",
    "FieldInstance",
    "load_definitions",
    "get_field_header_from_name",
    "get_field_name_from_header",
    "get_field_instance",
    "get_ledger_entry_type_code",
    "get_ledger_entry_type_name",
    "get_transaction_result_code",
    "get_transaction_result_name",
    "get_transaction_type_code",
    "get_transaction_type_name",
]
