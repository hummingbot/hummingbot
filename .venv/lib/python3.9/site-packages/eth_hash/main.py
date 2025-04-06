from typing import (
    Union,
)

from .abc import (
    BackendAPI,
    PreImageAPI,
)


class Keccak256:
    def __init__(self, backend: BackendAPI) -> None:
        self._backend = backend
        self.hasher = self._hasher_first_run
        self.preimage = self._preimage_first_run

    def _hasher_first_run(self, in_data: Union[bytearray, bytes]) -> bytes:
        """
        Validate, on first-run, that the hasher backend is valid.

        After first run, replace this with the new hasher method.
        This is a bit of a hacky way to minimize overhead on hash calls after
        this first one.
        """
        # Execute directly before saving method,
        # to let any side-effects settle (see AutoBackend)
        result = self._backend.keccak256(in_data)
        new_hasher = self._backend.keccak256
        assert (
            new_hasher(b"")
            == b"\xc5\xd2F\x01\x86\xf7#<\x92~}\xb2\xdc\xc7\x03\xc0\xe5\x00\xb6S\xca\x82';\x7b\xfa\xd8\x04]\x85\xa4p"  # noqa: E501
        )
        self.hasher = new_hasher
        return result

    def _preimage_first_run(self, in_data: Union[bytearray, bytes]) -> PreImageAPI:
        # Execute directly before saving method,
        # to let any side-effects settle (see AutoBackend)
        result = self._backend.preimage(in_data)
        self.preimage = self._backend.preimage
        return result

    def __call__(self, preimage: Union[bytearray, bytes]) -> bytes:
        if not isinstance(preimage, (bytearray, bytes)):
            raise TypeError(
                "Can only compute the hash of `bytes` or `bytearray` values, "
                f"not {repr(preimage)}"
            )

        return self.hasher(preimage)

    def new(self, preimage: Union[bytearray, bytes]) -> PreImageAPI:
        if not isinstance(preimage, (bytearray, bytes)):
            raise TypeError(
                "Can only compute the hash of `bytes` or `bytearray` values, "
                f"not {repr(preimage)}"
            )
        return self.preimage(preimage)
