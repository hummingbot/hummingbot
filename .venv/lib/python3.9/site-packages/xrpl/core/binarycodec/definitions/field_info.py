"""Model object for field info from the "fields" section of definitions.json."""

from __future__ import annotations  # Requires Python 3.7+

from typing_extensions import Self


class FieldInfo:
    """Model object for field info metadata from the "fields" section of
    definitions.json.
    """

    def __init__(
        self: Self,
        nth: int,
        is_variable_length_encoded: bool,
        is_serialized: bool,
        is_signing_field: bool,
        type_name: str,
    ) -> None:
        """
        :param nth: The field code -- sort order position for fields of the same type.
        :param is_variable_length_encoded: Whether the serialized length of this field
        varies.
        :param is_serialized: If the field is presented in binary serialized
        representation.
        :param is_signing_field: If the field should be included in signed transactions.
        :param type_name: The name of this field's serialization type,
        e.g. UInt32, AccountID, etc.
        """
        self.nth = nth
        self.is_variable_length_encoded = is_variable_length_encoded
        self.is_serialized = is_serialized
        self.is_signing_field = is_signing_field
        self.type = type_name
