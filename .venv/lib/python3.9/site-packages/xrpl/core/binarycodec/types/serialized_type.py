"""The base class for all binary codec field types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Type

from typing_extensions import Self

if TYPE_CHECKING:
    # To prevent a circular dependency.
    from xrpl.core.binarycodec.binary_wrappers.binary_parser import BinaryParser


class SerializedType(ABC):
    """The base class for all binary codec field types."""

    def __init__(self: Self, buffer: bytes = bytes()) -> None:
        """Construct a new SerializedType."""
        self.buffer = buffer

    @classmethod
    @abstractmethod
    def from_parser(  # noqa: D102
        cls: Type[Self],
        parser: BinaryParser,
        # length_hint is Any so that subclasses can choose whether or not to require it.
        length_hint: Any,  # noqa: ANN401
    ) -> Self:
        pass

    @classmethod
    @abstractmethod
    def from_value(cls: Type[Self], value: Any) -> Self:  # noqa: D102, ANN401
        # Note: Its difficult to specify a concrete type for value parameter because
        # child-classes accept a variety of types.
        pass

    def to_byte_sink(self: Self, bytesink: bytearray) -> None:
        """
        Write the bytes representation of a SerializedType to a bytearray.

        Args:
            bytesink: The bytearray to write self.buffer to.

        Returns: None
        """
        bytesink.extend(self.buffer)

    def __bytes__(self: Self) -> bytes:
        """
        Get the bytes representation of a SerializedType.

        Returns:
            The bytes representation of the SerializedType.
        """
        return self.buffer

    def to_json(self: Self) -> Any:  # noqa: ANN401
        """
        Returns the JSON representation of a SerializedType.

        If not overridden, returns hex string representation of bytes.

        Returns:
            The JSON representation of the SerializedType.
        """
        return self.to_hex()

    def __str__(self: Self) -> str:
        """
        Returns the hex string representation of self.buffer.

        Returns:
            The hex string representation of self.buffer.
        """
        return self.to_hex()

    def to_hex(self: Self) -> str:
        """
        Get the hex representation of a SerializedType's bytes.

        Returns:
            The hex string representation of the SerializedType's bytes.
        """
        return self.buffer.hex().upper()

    def __len__(self: Self) -> int:
        """Get the length of a SerializedType's bytes."""
        return len(self.buffer)
