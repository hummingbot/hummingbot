from eth_utils import (
    big_endian_to_int,
    int_to_big_endian,
)

from rlp.exceptions import (
    DeserializationError,
    SerializationError,
)


class BigEndianInt:
    """
    A sedes for big endian integers.

    :param l: the size of the serialized representation in bytes or `None` to
              use the shortest possible one
    """

    def __init__(self, length=None):
        self.length = length

    def serialize(self, obj):
        if isinstance(obj, bool) or not isinstance(obj, int):
            raise SerializationError("Can only serialize integers", obj)
        if self.length is not None and obj >= 256**self.length:
            raise SerializationError(
                f"Integer too large (does not fit in {self.length} bytes)",
                obj,
            )
        if obj < 0:
            raise SerializationError("Cannot serialize negative integers", obj)

        if obj == 0:
            s = b""
        else:
            s = int_to_big_endian(obj)

        if self.length is not None:
            return b"\x00" * max(0, self.length - len(s)) + s
        else:
            return s

    def deserialize(self, serial):
        if self.length is not None and len(serial) != self.length:
            raise DeserializationError("Invalid serialization (wrong size)", serial)
        if self.length is None and len(serial) > 0 and serial[0:1] == b"\x00":
            raise DeserializationError(
                "Invalid serialization (not minimal " "length)", serial
            )

        serial = serial or b"\x00"
        return big_endian_to_int(serial)


big_endian_int = BigEndianInt()
