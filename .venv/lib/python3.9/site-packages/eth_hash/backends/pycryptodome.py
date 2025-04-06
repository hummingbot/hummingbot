from typing import (
    Union,
    cast,
)

from Crypto.Hash import (
    keccak,
)

from eth_hash.abc import (
    BackendAPI,
    PreImageAPI,
)


class CryptodomePreimage(PreImageAPI):
    def __init__(self, prehash: bytes) -> None:
        self._hash = keccak.new(data=prehash, digest_bits=256, update_after_digest=True)
        # pycryptodome doesn't expose a `copy` mechanism for it's hash objects
        # so we keep a record of all of the parts for when/if we need to copy
        # them.
        self._parts = [prehash]

    def update(self, prehash: bytes) -> None:
        self._hash.update(prehash)
        self._parts.append(prehash)

    def digest(self) -> bytes:
        return cast(bytes, self._hash.digest())

    def copy(self) -> "CryptodomePreimage":
        return CryptodomePreimage(b"".join(self._parts))


class CryptodomeBackend(BackendAPI):
    def keccak256(self, prehash: Union[bytearray, bytes]) -> bytes:
        hasher = keccak.new(data=prehash, digest_bits=256)
        return cast(bytes, hasher.digest())

    def preimage(self, prehash: Union[bytearray, bytes]) -> PreImageAPI:
        return CryptodomePreimage(prehash)


backend = CryptodomeBackend()
keccak256 = backend.keccak256
preimage = backend.preimage
