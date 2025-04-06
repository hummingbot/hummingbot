"""
Types used for BLS Signatures.
"""

from typing import (
    NewType,
)

BLSPubkey = NewType("BLSPubkey", bytes)
"""
A BLS public key that is 48 bytes in length.
"""
BLSPrivateKey = NewType("BLSPrivateKey", int)
"""
A BLS private key integer value.
"""
BLSSignature = NewType("BLSSignature", bytes)
"""
A BLS signature that is 96 bytes in length.
"""
