import re
from json import JSONEncoder
from typing import Any, Union, Type

from eth_utils.crypto import keccak
from eth_utils.conversions import to_bytes, to_hex, to_int


class EIP712Type:
    """The base type for members of a struct.

    Generally you wouldn't use this - instead, see the subclasses below. Or you may want an EIP712Struct instead.
    """
    def __init__(self, type_name: str, none_val: Any):
        self.type_name = type_name
        self.none_val = none_val

    def encode_value(self, value) -> bytes:
        """Given a value, verify it and convert into the format required by the spec.

        :param value: A correct input value for the implemented type.
        :return: A 32-byte object containing encoded data
        """
        if value is None:
            return self._encode_value(self.none_val)
        else:
            return self._encode_value(value)

    def _encode_value(self, value) -> bytes:
        """Must be implemented by subclasses, handles value encoding on a case-by-case basis.

        Don't call this directly - use ``.encode_value(value)`` instead.
        """
        pass

    def __eq__(self, other):
        self_type = getattr(self, 'type_name')
        other_type = getattr(other, 'type_name')

        return self_type is not None and self_type == other_type

    def __hash__(self):
        return hash(self.type_name)


class Array(EIP712Type):
    def __init__(self, member_type: Union[EIP712Type, Type[EIP712Type]], fixed_length: int = 0):
        """Represents an array member type.

        Example:
            a1 = Array(String())     # string[] a1
            a2 = Array(String(), 8)  # string[8] a2
            a3 = Array(MyStruct)     # MyStruct[] a3
        """
        fixed_length = int(fixed_length)
        if fixed_length == 0:
            type_name = f'{member_type.type_name}[]'
        else:
            type_name = f'{member_type.type_name}[{fixed_length}]'
        self.member_type = member_type
        self.fixed_length = fixed_length
        super(Array, self).__init__(type_name, [])

    def _encode_value(self, value):
        """Arrays are encoded by concatenating their encoded contents, and taking the keccak256 hash."""
        encoder = self.member_type
        encoded_values = [encoder.encode_value(v) for v in value]
        return keccak(b''.join(encoded_values))


class Address(EIP712Type):
    def __init__(self):
        """Represents an ``address`` type."""
        super(Address, self).__init__('address', 0)

    def _encode_value(self, value):
        """Addresses are encoded like Uint160 numbers."""

        # Some smart conversions - need to get the address to a numeric before we encode it
        if isinstance(value, bytes):
            v = to_int(value)
        elif isinstance(value, str):
            v = to_int(hexstr=value)
        else:
            v = value  # Fallback, just use it as-is.
        return Uint(160).encode_value(v)


class Boolean(EIP712Type):
    def __init__(self):
        """Represents a ``bool`` type."""
        super(Boolean, self).__init__('bool', False)

    def _encode_value(self, value):
        """Booleans are encoded like the uint256 values of 0 and 1."""
        if value is False:
            return Uint(256).encode_value(0)
        elif value is True:
            return Uint(256).encode_value(1)
        else:
            raise ValueError(f'Must be True or False. Got: {value}')


class Bytes(EIP712Type):
    def __init__(self, length: int = 0):
        """Represents a solidity bytes type.

        Length may be used to specify a static ``bytesN`` type. Or 0 for a dynamic ``bytes`` type.
        Example:
            b1 = Bytes()    # bytes b1
            b2 = Bytes(10)  # bytes10 b2

        ``length`` MUST be between 0 and 32, or a ValueError is raised.
        """
        length = int(length)
        if length == 0:
            # Special case: Length of 0 means a dynamic bytes type
            type_name = 'bytes'
        elif 1 <= length <= 32:
            type_name = f'bytes{length}'
        else:
            raise ValueError(f'Byte length must be between 1 or 32. Got: {length}')
        self.length = length
        super(Bytes, self).__init__(type_name, b'')

    def _encode_value(self, value):
        """Static bytesN types are encoded by right-padding to 32 bytes. Dynamic bytes types are keccak256 hashed."""
        if isinstance(value, str):
            # Try converting to a bytestring, assuming that it's been given as hex
            value = to_bytes(hexstr=value)

        if self.length == 0:
            return keccak(value)
        else:
            if len(value) > self.length:
                raise ValueError(f'{self.type_name} was given bytes with length {len(value)}')
            padding = bytes(32 - len(value))
            return value + padding


class Int(EIP712Type):
    def __init__(self, length: int = 256):
        """Represents a signed int type. Length may be given to specify the int length in bits. Default length is 256

        Example:
            i1 = Int(256)  # int256 i1
            i2 = Int()     # int256 i2
            i3 = Int(128)  # int128 i3
        """
        length = int(length)
        if length < 8 or length > 256 or length % 8 != 0:
            raise ValueError(f'Int length must be a multiple of 8, between 8 and 256. Got: {length}')
        self.length = length
        super(Int, self).__init__(f'int{length}', 0)

    def _encode_value(self, value: int):
        """Ints are encoded by padding them to 256-bit representations."""
        value.to_bytes(self.length // 8, byteorder='big', signed=True)  # For validation
        return value.to_bytes(32, byteorder='big', signed=True)


class String(EIP712Type):
    def __init__(self):
        """Represents a string type."""
        super(String, self).__init__('string', '')

    def _encode_value(self, value):
        """Strings are encoded by taking the keccak256 hash of their contents."""
        return keccak(text=value)


class Uint(EIP712Type):
    def __init__(self, length: int = 256):
        """Represents an unsigned int type. Length may be given to specify the int length in bits. Default length is 256

        Example:
            ui1 = Uint(256)  # uint256 ui1
            ui2 = Uint()     # uint256 ui2
            ui3 = Uint(128)  # uint128 ui3
        """
        length = int(length)
        if length < 8 or length > 256 or length % 8 != 0:
            raise ValueError(f'Uint length must be a multiple of 8, between 8 and 256. Got: {length}')
        self.length = length
        super(Uint, self).__init__(f'uint{length}', 0)

    def _encode_value(self, value: int):
        """Uints are encoded by padding them to 256-bit representations."""
        value.to_bytes(self.length // 8, byteorder='big', signed=False)  # For validation
        return value.to_bytes(32, byteorder='big', signed=False)


# This helper dict maps solidity's type names to our EIP712Type classes
solidity_type_map = {
    'address': Address,
    'bool': Boolean,
    'bytes': Bytes,
    'int': Int,
    'string': String,
    'uint': Uint,
}


def from_solidity_type(solidity_type: str):
    """Convert a string into the EIP712Type implementation. Basic types only."""
    pattern = r'([a-z]+)(\d+)?(\[(\d+)?\])?'
    match = re.match(pattern, solidity_type)

    if match is None:
        return None

    type_name = match.group(1)  # The type name, like the "bytes" in "bytes32"
    opt_len = match.group(2)    # An optional length spec, like the "32" in "bytes32"
    is_array = match.group(3)   # Basically just checks for square brackets
    array_len = match.group(4)  # For fixed length arrays only, this is the length

    if type_name not in solidity_type_map:
        # Only supporting basic types here - return None if we don't recognize it.
        return None

    # Construct the basic type
    base_type = solidity_type_map[type_name]
    if opt_len:
        type_instance = base_type(int(opt_len))
    else:
        type_instance = base_type()

    if is_array:
        # Nest the aforementioned basic type into an Array.
        if array_len:
            result = Array(type_instance, int(array_len))
        else:
            result = Array(type_instance)
        return result
    else:
        return type_instance


class BytesJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, bytes):
            return to_hex(o)
        else:
            return super(BytesJSONEncoder, self).default(o)
