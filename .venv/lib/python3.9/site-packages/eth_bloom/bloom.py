import numbers
import operator
from typing import (
    TYPE_CHECKING,
    Iterable,
    Union,
)

from eth_hash.auto import (
    keccak as keccak_256,
)


def get_chunks_for_bloom(value_hash: bytes) -> Iterable[bytes]:
    yield value_hash[:2]
    yield value_hash[2:4]
    yield value_hash[4:6]


def chunk_to_bloom_bits(chunk: bytes) -> int:
    high, low = bytearray(chunk)
    return 1 << ((low + (high << 8)) & 2047)


def get_bloom_bits(value: bytes) -> Iterable[int]:
    value_hash = keccak_256(value)
    for chunk in get_chunks_for_bloom(value_hash):
        bloom_bits = chunk_to_bloom_bits(chunk)
        yield bloom_bits


class BloomFilter(numbers.Number):
    value = None  # type: int

    def __init__(self, value: int = 0) -> None:
        self.value = value

    def __int__(self) -> int:
        return self.value

    def __hash__(self) -> int:
        return hash(self.value)

    def add(self, value: bytes) -> None:
        if not isinstance(value, bytes):
            raise TypeError("Value must be of type `bytes`")
        for bloom_bits in get_bloom_bits(value):
            self.value |= bloom_bits

    def extend(self, iterable: Iterable[bytes]) -> None:
        for value in iterable:
            self.add(value)

    @classmethod
    def from_iterable(cls, iterable: Iterable[bytes]) -> "BloomFilter":
        bloom = cls()
        bloom.extend(iterable)
        return bloom

    def __contains__(self, value: bytes) -> bool:
        if not isinstance(value, bytes):
            raise TypeError("Value must be of type `bytes`")
        return all(self.value & bloom_bits for bloom_bits in get_bloom_bits(value))

    def __index__(self) -> int:
        return operator.index(self.value)

    def _combine(self, other: Union[int, "BloomFilter"]) -> "BloomFilter":
        if not isinstance(other, (int, BloomFilter)):
            raise TypeError(
                "The `or` operator is only supported for other `BloomFilter` instances"
            )
        return type(self)(int(self) | int(other))

    def __or__(self, other: Union[int, "BloomFilter"]) -> "BloomFilter":
        return self._combine(other)

    def __add__(self, other: Union[int, "BloomFilter"]) -> "BloomFilter":
        return self._combine(other)

    def _icombine(self, other: Union[int, "BloomFilter"]) -> "BloomFilter":
        if not isinstance(other, (int, BloomFilter)):
            raise TypeError(
                "The `or` operator is only supported for other `BloomFilter` instances"
            )
        self.value |= int(other)
        return self

    def __ior__(self, other: Union[int, "BloomFilter"]) -> "BloomFilter":
        return self._icombine(other)

    def __iadd__(self, other: Union[int, "BloomFilter"]) -> "BloomFilter":
        return self._icombine(other)


if TYPE_CHECKING:
    # This ensures that our linter catches any missing abstract base methods
    BloomFilter()
