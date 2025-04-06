"""
Module for sedes objects that use lists as serialization format.
"""
from collections.abc import (
    Sequence,
)

from eth_utils import (
    to_list,
    to_tuple,
)

from rlp.exceptions import (
    DeserializationError,
    ListDeserializationError,
    ListSerializationError,
    SerializationError,
)

from .binary import (
    Binary as BinaryClass,
)


def is_sedes(obj):
    """
    Check if `obj` is a sedes object.

    A sedes object is characterized by having the methods `serialize(obj)` and
    `deserialize(serial)`.
    """
    return hasattr(obj, "serialize") and hasattr(obj, "deserialize")


def is_sequence(obj):
    """Check if `obj` is a sequence, but not a string or bytes."""
    return isinstance(obj, Sequence) and not (
        isinstance(obj, str) or BinaryClass.is_valid_type(obj)
    )


class List(list):
    """
    A sedes for lists, implemented as a list of other sedes objects.

    :param strict: If true (de)serializing lists that have a length not
                   matching the sedes length will result in an error. If false
                   (de)serialization will stop as soon as either one of the
                   lists runs out of elements.
    """

    def __init__(self, elements=None, strict=True):
        super().__init__()
        self.strict = strict

        if elements:
            for e in elements:
                if is_sedes(e):
                    self.append(e)
                elif isinstance(e, Sequence):
                    self.append(List(e))
                else:
                    raise TypeError(
                        "Instances of List must only contain sedes objects or "
                        "nested sequences thereof."
                    )

    @to_list
    def serialize(self, obj):
        if not is_sequence(obj):
            raise ListSerializationError("Can only serialize sequences", obj)
        if self.strict and len(self) != len(obj):
            raise ListSerializationError(
                "Serializing list length (%d) does not match sedes (%d)"
                % (len(obj), len(self)),
                obj,
            )

        for index, (element, sedes) in enumerate(zip(obj, self)):
            try:
                yield sedes.serialize(element)
            except SerializationError as e:
                raise ListSerializationError(obj=obj, element_exception=e, index=index)

    @to_tuple
    def deserialize(self, serial):
        if not is_sequence(serial):
            raise ListDeserializationError("Can only deserialize sequences", serial)

        if self.strict and len(serial) != len(self):
            raise ListDeserializationError(
                "Deserializing list length (%d) does not match sedes (%d)"
                % (len(serial), len(self)),
                serial,
            )

        for idx, (sedes, element) in enumerate(zip(self, serial)):
            try:
                yield sedes.deserialize(element)
            except DeserializationError as e:
                raise ListDeserializationError(
                    serial=serial, element_exception=e, index=idx
                )


class CountableList:
    """
    A sedes for lists of arbitrary length.

    :param element_sedes: when (de-)serializing a list, this sedes will be
                          applied to all of its elements
    :param max_length: maximum number of allowed elements, or `None` for no limit
    """

    def __init__(self, element_sedes, max_length=None):
        self.element_sedes = element_sedes
        self.max_length = max_length

    @to_list
    def serialize(self, obj):
        if not is_sequence(obj):
            raise ListSerializationError("Can only serialize sequences", obj)

        if self.max_length is not None and len(obj) > self.max_length:
            raise ListSerializationError(
                f"Too many elements ({len(obj)}, allowed {self.max_length})",
                obj=obj,
            )

        for index, element in enumerate(obj):
            try:
                yield self.element_sedes.serialize(element)
            except SerializationError as e:
                raise ListSerializationError(obj=obj, element_exception=e, index=index)

    @to_tuple
    def deserialize(self, serial):
        if not is_sequence(serial):
            raise ListDeserializationError(
                "Can only deserialize sequences", serial=serial
            )
        for index, element in enumerate(serial):
            if self.max_length is not None and index >= self.max_length:
                raise ListDeserializationError(
                    f"Too many elements (more than {self.max_length})",
                    serial=serial,
                )

            try:
                yield self.element_sedes.deserialize(element)
            except DeserializationError as e:
                raise ListDeserializationError(
                    serial=serial, element_exception=e, index=index
                )
