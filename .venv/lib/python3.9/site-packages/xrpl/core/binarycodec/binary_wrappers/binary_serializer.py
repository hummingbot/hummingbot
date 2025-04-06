"""Context manager and helpers for the serialization of a JSON object into bytes."""

from __future__ import annotations  # Requires Python 3.7+

from typing_extensions import Final, Self

from xrpl.core.binarycodec.definitions.field_instance import FieldInstance
from xrpl.core.binarycodec.types.serialized_type import SerializedType

# Constants used in length prefix encoding:
# max length that can be represented in a single byte per XRPL serialization encoding
_MAX_SINGLE_BYTE_LENGTH: Final[int] = 192
# max length that can be represented in 2 bytes per XRPL serialization encoding
_MAX_DOUBLE_BYTE_LENGTH: Final[int] = 12481
# max value that can be used in the second byte of a length field
_MAX_SECOND_BYTE_VALUE: Final[int] = 240
# maximum length that can be encoded in a length prefix per XRPL serialization encoding
_MAX_LENGTH_VALUE: Final[int] = 918744


def _encode_variable_length_prefix(length: int) -> bytes:
    """
    Helper function for length-prefixed fields including Blob types
    and some AccountID types. Calculates the prefix of variable length bytes.

    The length of the prefix is 1-3 bytes depending on the length of the contents:
    Content length <= 192 bytes: prefix is 1 byte
    192 bytes < Content length <= 12480 bytes: prefix is 2 bytes
    12480 bytes < Content length <= 918744 bytes: prefix is 3 bytes

    `See Length Prefixing <https://xrpl.org/serialization.html#length-prefixing>`_
    """
    if length <= _MAX_SINGLE_BYTE_LENGTH:
        return length.to_bytes(1, byteorder="big", signed=False)
    if length < _MAX_DOUBLE_BYTE_LENGTH:
        length -= _MAX_SINGLE_BYTE_LENGTH + 1
        byte1 = ((length >> 8) + (_MAX_SINGLE_BYTE_LENGTH + 1)).to_bytes(
            1, byteorder="big", signed=False
        )
        byte2 = (length & 0xFF).to_bytes(1, byteorder="big", signed=False)
        return byte1 + byte2
    if length <= _MAX_LENGTH_VALUE:
        length -= _MAX_DOUBLE_BYTE_LENGTH
        byte1 = ((_MAX_SECOND_BYTE_VALUE + 1) + (length >> 16)).to_bytes(
            1, byteorder="big", signed=False
        )
        byte2 = ((length >> 8) & 0xFF).to_bytes(1, byteorder="big", signed=False)
        byte3 = (length & 0xFF).to_bytes(1, byteorder="big", signed=False)
        return byte1 + byte2 + byte3

    raise ValueError(f"VariableLength field must be <= {_MAX_LENGTH_VALUE} bytes long")


class BinarySerializer:
    """Serializes JSON to XRPL binary format."""

    def __init__(self: Self) -> None:
        """Construct a BinarySerializer."""
        self.bytesink = bytes()

    def append(self: Self, bytes_object: bytes) -> None:
        """
        Write given bytes to this BinarySerializer's bytesink.

        Args:
            bytes_object: The bytes to write to bytesink.
        """
        self.bytesink += bytes_object

    def __bytes__(self: Self) -> bytes:
        """
        Get the bytes representation of a BinarySerializer.

        Returns:
            The bytes representation of the BinarySerializer's bytesink.
        """
        return self.bytesink

    def write_length_encoded(
        self: Self,
        value: SerializedType,
        encode_value: bool = True,
    ) -> None:
        """
        Write a variable length encoded value to the BinarySerializer.

        Args:
            value: The SerializedType object to write to bytesink.
            encode_value: Does not encode the value; just encodes `00` in its place.
                Used in the UNLModify encoding workaround. The default is True.
        """
        byte_object = bytearray()
        if encode_value:
            value.to_byte_sink(byte_object)
        length_prefix = _encode_variable_length_prefix(len(byte_object))
        self.bytesink += length_prefix
        self.bytesink += byte_object

    def write_field_and_value(
        self: Self,
        field: FieldInstance,
        value: SerializedType,
        is_unl_modify_workaround: bool = False,
    ) -> None:
        """
        Write field and value to the buffer.

        Args:
            field: The field to write to the buffer.
            value: The value to write to the buffer.
            is_unl_modify_workaround: Encode differently for UNLModify
                pseudotransactions, due to a bug in rippled. Only True for the Account
                field in UNLModify pseudotransactions. The default is False.
        """
        self.bytesink += bytes(field.header)

        if field.is_variable_length_encoded:
            self.write_length_encoded(value, not is_unl_modify_workaround)
        else:
            self.bytesink += bytes(value)
