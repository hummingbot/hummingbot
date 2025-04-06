"""A container class for simultaneous storage of a field's type code and field code."""

from __future__ import annotations  # Requires Python 3.7+

from typing_extensions import Self


class FieldHeader:
    """A container class for simultaneous storage of a field's type code and
    field code.
    """

    def __init__(self: Self, type_code: int, field_code: int) -> None:
        """
        Construct a FieldHeader.
        `See Field Order <https://xrpl.org/serialization.html#canonical-field-order>`_

        :param type_code: The code for this field's serialization type.
        :param field_code: The sort code that orders fields of the same type.
        """
        self.type_code = type_code
        self.field_code = field_code

    def __eq__(self: Self, other: object) -> bool:
        """Two FieldHeaders are equal if both type code and field_code are the same."""
        if not isinstance(other, FieldHeader):
            return NotImplemented
        return self.type_code == other.type_code and self.field_code == other.field_code

    def __hash__(self: Self) -> int:
        """Two equal FieldHeaders must have the same hash value."""
        return hash((self.type_code, self.field_code))

    def __bytes__(self: Self) -> bytes:
        """
        Get the bytes representation of a FieldHeader.

        Returns:
            The bytes representation of the FieldHeader.
        """
        header = []
        if self.type_code < 16:
            if self.field_code < 16:
                header.append(self.type_code << 4 | self.field_code)
            else:
                header.append(self.type_code << 4)
                header.append(self.field_code)
        elif self.field_code < 16:
            header += [self.field_code, self.type_code]
        else:
            header += [0, self.type_code, self.field_code]

        return bytes(header)

    def __repr__(self: Self) -> str:
        """Print a string representation of a FieldHeader (for debugging)."""
        return f"FieldHeader({self.type_code}, {self.field_code})"
