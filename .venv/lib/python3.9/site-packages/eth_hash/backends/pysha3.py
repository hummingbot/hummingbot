from typing import (
    Union,
)

from sha3 import (
    keccak_256 as _keccak_256,
)

from eth_hash.abc import (
    BackendAPI,
    PreImageAPI,
)


class Pysha3Preimage(PreImageAPI):
    def __init__(self, prehash: bytes) -> None:
        self._hash = _keccak_256(prehash)

    def update(self, prehash: bytes) -> None:
        return self._hash.update(prehash)  # type: ignore

    def digest(self) -> bytes:
        return self._hash.digest()  # type: ignore

    def copy(self) -> "Pysha3Preimage":
        dup = Pysha3Preimage(b"")
        dup._hash = self._hash.copy()
        return dup


class PySha3Backend(BackendAPI):
    def keccak256(self, prehash: Union[bytearray, bytes]) -> bytes:
        return _keccak_256(prehash).digest()  # type: ignore

    def preimage(self, prehash: Union[bytearray, bytes]) -> PreImageAPI:
        return Pysha3Preimage(prehash)


backend = PySha3Backend()
keccak256 = backend.keccak256
preimage = backend.preimage
