#  Copyright (C) 2012-2016 Christian Heimes (christian@python.org)
#  Licensed to PSF under a Contributor Agreement.
#

# monkey patch _hashlib
import hashlib as _hashlib

from _pysha3 import keccak_224, keccak_256, keccak_384, keccak_512
from _pysha3 import sha3_224, sha3_256, sha3_384, sha3_512
from _pysha3 import shake_128, shake_256


__all__ = ("sha3_224", "sha3_256", "sha3_384", "sha3_512",
           "keccak_224", "keccak_256", "keccak_384", "keccak_512",
           "shake_128", "shake_256")


if not hasattr(_hashlib, "sha3_512"):
    _hashlib.sha3_224 = sha3_224
    _hashlib.sha3_256 = sha3_256
    _hashlib.sha3_384 = sha3_384
    _hashlib.sha3_512 = sha3_512
    _hashlib.shake_128 = shake_128
    _hashlib.shake_256 = shake_256
