"""Context manager and helpers for the deserialization of bytes into JSON."""

from __future__ import annotations  # Requires Python 3.7+

from typing import TYPE_CHECKING, Optional, Tuple, Type, cast

from typing_extensions import Final, Self

from xrpl.core.binarycodec.definitions import definitions
from xrpl.core.binarycodec.definitions.field_header import FieldHeader
from xrpl.core.binarycodec.definitions.field_instance import FieldInstance
from xrpl.core.binarycodec.exceptions import XRPLBinaryCodecException

if TYPE_CHECKING:
    # To prevent a circular dependency.
    from xrpl.core.binarycodec.types.serialized_type import SerializedType

# Constants used in length prefix decoding:
# Max length that can be represented in a single byte per XRPL serialization encoding
_MAX_SINGLE_BYTE_LENGTH: Final[int] = 192
# Max length that can be represented in 2 bytes per XRPL serialization restrictions
_MAX_DOUBLE_BYTE_LENGTH: Final[int] = 12481
# Max value that can be used in the second byte of a length field
_MAX_SECOND_BYTE_VALUE: Final[int] = 240
# Max value that can be represented using one 8-bit byte (2^8)
_MAX_BYTE_VALUE: Final[int] = 256
# Max value that can be represented in using two 8-bit bytes (2^16)
_MAX_DOUBLE_BYTE_VALUE: Final[int] = 65536


class BinaryParser:
    """Deserializes from hex-encoded XRPL binary format to JSON fields and values."""

    def __init__(self: Self, hex_bytes: str) -> None:
        """Construct a BinaryParser that will parse hex-encoded bytes."""
        self.bytes = bytes.fromhex(hex_bytes)

    def __len__(self: Self) -> int:
        """Return the number of bytes in this parser's buffer."""
        return len(self.bytes)

    def peek(self: Self) -> Optional[bytes]:
        """
        Peek the first byte of the BinaryParser.

        Returns:
            The first byte of the BinaryParser.
        """
        if len(self.bytes) > 0:
            return cast(bytes, self.bytes[0])
        return None

    def skip(self: Self, n: int) -> None:
        """
        Consume the first n bytes of the BinaryParser.

        Args:
            n: The number of bytes to consume.

        Raises:
            XRPLBinaryCodecException: If n bytes can't be skipped.
        """
        if n > len(self.bytes):
            raise XRPLBinaryCodecException(
                f"BinaryParser can't skip {n} bytes, only contains {len(self.bytes)}."
            )
        self.bytes = self.bytes[n:]

    def read(self: Self, n: int) -> bytes:
        """
        Consume and return the first n bytes of the BinaryParser.

        Args:
            n: The number of bytes to read.

        Returns:
            The bytes read.
        """
        first_n_bytes = self.bytes[:n]
        self.skip(n)
        return first_n_bytes

    def read_uint8(self: Self) -> int:
        """
        Read 1 byte from parser and return as unsigned int.

        Returns:
            The byte read.
        """
        return int.from_bytes(self.read(1), byteorder="big", signed=False)

    def read_uint16(self: Self) -> int:
        """
        Read 2 bytes from parser and return as unsigned int.

        Returns:
            The bytes read.
        """
        return int.from_bytes(self.read(2), byteorder="big", signed=False)

    def read_uint32(self: Self) -> int:
        """
        Read 4 bytes from parser and return as unsigned int.

        Returns:
            The bytes read.
        """
        return int.from_bytes(self.read(4), byteorder="big", signed=False)

    def is_end(self: Self, custom_end: Optional[int] = None) -> bool:
        """
        Returns whether the binary parser has finished parsing (e.g. there is nothing
        left in the buffer that needs to be processed).

        Args:
            custom_end: An ending byte-phrase.

        Returns:
            Whether or not it's the end.
        """
        return len(self.bytes) == 0 or (
            custom_end is not None and len(self.bytes) <= custom_end
        )

    def read_variable_length(self: Self) -> bytes:
        """
        Reads and returns variable length encoded bytes.

        Returns:
            The bytes read.
        """
        return self.read(self._read_length_prefix())

    def _read_length_prefix(self: Self) -> int:
        """
        Reads a variable length encoding prefix and returns the encoded length.

        The formula for decoding a length prefix is described in:
        `Length Prefixing <https://xrpl.org/serialization.html#length-prefixing>`_
        """
        byte1 = self.read_uint8()
        # If the field contains 0 to 192 bytes of data, the first byte defines
        # the length of the contents
        if byte1 <= _MAX_SINGLE_BYTE_LENGTH:
            return byte1
        # If the field contains 193 to 12480 bytes of data, the first two bytes
        # indicate the length of the field with the following formula:
        #    193 + ((byte1 - 193) * 256) + byte2
        if byte1 <= _MAX_SECOND_BYTE_VALUE:
            byte2 = self.read_uint8()
            return (
                (_MAX_SINGLE_BYTE_LENGTH + 1)
                + ((byte1 - (_MAX_SINGLE_BYTE_LENGTH + 1)) * _MAX_BYTE_VALUE)
                + byte2
            )
        # If the field contains 12481 to 918744 bytes of data, the first three
        # bytes indicate the length of the field with the following formula:
        #    12481 + ((byte1 - 241) * 65536) + (byte2 * 256) + byte3
        if byte1 <= 254:
            byte2 = self.read_uint8()
            byte3 = self.read_uint8()
            return (
                _MAX_DOUBLE_BYTE_LENGTH
                + ((byte1 - (_MAX_SECOND_BYTE_VALUE + 1)) * _MAX_DOUBLE_BYTE_VALUE)
                + (byte2 * _MAX_BYTE_VALUE)
                + byte3
            )
        raise XRPLBinaryCodecException(
            "Length prefix must contain between 1 and 3 bytes."
        )

    def read_field_header(self: Self) -> FieldHeader:
        """
        Reads field ID from BinaryParser and returns as a FieldHeader object.

        Returns:
            The field header.

        Raises:
            XRPLBinaryCodecException: If the field ID cannot be read.
        """
        type_code = self.read_uint8()
        field_code = type_code & 15
        type_code >>= 4

        if type_code == 0:
            type_code = self.read_uint8()
            if type_code == 0 or type_code < 16:
                raise XRPLBinaryCodecException(
                    "Cannot read field ID, type_code out of range."
                )

        if field_code == 0:
            field_code = self.read_uint8()
            if field_code == 0 or field_code < 16:
                raise XRPLBinaryCodecException(
                    "Cannot read field ID, field_code out of range."
                )
        return FieldHeader(type_code, field_code)

    def read_field(self: Self) -> FieldInstance:
        """
        Read the field ordinal at the head of the BinaryParser and return a
        FieldInstance object representing information about the field contained
        in the following bytes.

        Returns:
            The field ordinal at the head of the BinaryParser.
        """
        field_header = self.read_field_header()
        field_name = definitions.get_field_name_from_header(field_header)
        return definitions.get_field_instance(field_name)

    def read_type(self: Self, field_type: Type[SerializedType]) -> SerializedType:
        """
        Read next bytes from BinaryParser as the given type.

        Args:
            field_type: The field type to read the next bytes as.

        Returns:
            None
        """
        return field_type.from_parser(self, None)

    def read_field_value(self: Self, field: FieldInstance) -> SerializedType:
        """
        Read value of the type specified by field from the BinaryParser.

        Args:
            field: The FieldInstance specifying the field to read.

        Returns:
            A SerializedType read from the BinaryParser.

        Raises:
            XRPLBinaryCodecException: If a parser cannot be constructed from field.
        """
        field_type = field.associated_type
        if field.is_variable_length_encoded:
            size_hint = self._read_length_prefix()
            value = field_type.from_parser(self, size_hint)
        else:
            value = field_type.from_parser(self, None)
        if value is None:
            raise XRPLBinaryCodecException(
                f"from_parser for {field.name}, {field.type} returned None."
            )
        return value

    def read_field_and_value(
        self: Self,
    ) -> Tuple[FieldInstance, SerializedType]:
        """
        Get the next field and value from the BinaryParser.

        Returns:
            A (FieldInstance, SerializedType) pair as read from the BinaryParser.
        """
        field = self.read_field()
        return field, self.read_field_value(field)
