from os import urandom
from threading import Lock
from typing import Optional

from coincurve.flags import CONTEXT_FLAGS, CONTEXT_NONE

from ._libsecp256k1 import ffi, lib


class Context:
    def __init__(self, seed: Optional[bytes] = None, flag=CONTEXT_NONE, name: str = ''):
        if flag not in CONTEXT_FLAGS:
            raise ValueError(f'{flag} is an invalid context flag.')
        self._lock = Lock()

        self.ctx = ffi.gc(lib.secp256k1_context_create(flag), lib.secp256k1_context_destroy)
        self.reseed(seed)

        self.name = name

    def reseed(self, seed: Optional[bytes] = None):
        """
        Protects against certain possible future side-channel timing attacks.
        """
        with self._lock:
            seed = urandom(32) if not seed or len(seed) != 32 else seed
            res = lib.secp256k1_context_randomize(self.ctx, ffi.new('unsigned char [32]', seed))
            if not res:
                raise ValueError('secp256k1_context_randomize')

    def __repr__(self):
        return self.name or super().__repr__()


GLOBAL_CONTEXT = Context(name='GLOBAL_CONTEXT')
