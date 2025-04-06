from typing import (
    Union,
)

from eth_hash.abc import (
    BackendAPI,
    PreImageAPI,
)
from eth_hash.utils import (
    auto_choose_backend,
)


class AutoBackend(BackendAPI):
    def _initialize(self) -> None:
        backend = auto_choose_backend()
        # Use setattr to circumvent mypy's confusion, see:
        # https://github.com/python/mypy/issues/2427
        setattr(self, "keccak256", backend.keccak256)  # noqa: B010
        setattr(self, "preimage", backend.preimage)  # noqa: B010

    def keccak256(self, in_data: Union[bytearray, bytes]) -> bytes:
        self._initialize()
        return self.keccak256(in_data)

    def preimage(self, in_data: Union[bytearray, bytes]) -> PreImageAPI:
        self._initialize()
        return self.preimage(in_data)
