"""A collection of serialization information about a specific field type."""

from __future__ import annotations  # Requires Python 3.7+

from typing import TYPE_CHECKING, Dict, Type

from typing_extensions import Self

from xrpl.core.binarycodec.definitions.field_header import FieldHeader
from xrpl.core.binarycodec.definitions.field_info import FieldInfo

if TYPE_CHECKING:
    # To prevent a circular dependency.
    from xrpl.core.binarycodec.types.serialized_type import SerializedType


def _get_type_by_name(name: str) -> Type[SerializedType]:
    """
    Convert the string name of a class to the class object itself.

    Args:
        name: the name of the class.

    Returns:
        The corresponding class object.
    """
    import xrpl.core.binarycodec.types as types

    type_map: Dict[str, Type[SerializedType]] = {
        name: object_type
        for (name, object_type) in types.__dict__.items()
        if name in types.__all__
    }

    return type_map[name]


class FieldInstance:
    """A collection of serialization information about a specific field type."""

    def __init__(
        self: Self,
        field_info: FieldInfo,
        field_name: str,
        field_header: FieldHeader,
    ) -> None:
        """
        Construct a FieldInstance.

        :param field_info: The field's serialization info from definitions.json.
        :param field_name: The field's string name.
        :param field_header: A FieldHeader object with the type_code and field_code.
        """
        self.nth = field_info.nth
        self.is_variable_length_encoded = field_info.is_variable_length_encoded
        self.is_serialized = field_info.is_serialized
        self.is_signing = field_info.is_signing_field
        self.type = field_info.type
        self.name = field_name
        self.header = field_header
        self.ordinal = self.header.type_code << 16 | self.nth
        self.associated_type = _get_type_by_name(self.type)
