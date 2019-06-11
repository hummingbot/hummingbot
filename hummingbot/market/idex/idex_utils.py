# Functions copied from pyethereum package to reduce dependencies

import binascii
import codecs
import coincurve
from Crypto.Hash import keccak
from py_ecc.secp256k1 import ecdsa_raw_sign
from rlp.sedes import big_endian_int
from typing import (
    Any,
    Dict,
    List
)

def str_to_bytes(value):
    if isinstance(value, bytearray):
        value = bytes(value)
    if isinstance(value, bytes):
        return value
    return bytes(value, 'utf-8')

def big_endian_to_int(x):
    return big_endian_int.deserialize(str_to_bytes(x).lstrip(b"\x00"))

def safe_ord(value) -> int:
    return value if isinstance(value, int) else ord(value)

def ecsign(rawhash, key):
    if coincurve and hasattr(coincurve, "PrivateKey"):
        pk = coincurve.PrivateKey(key)
        signature = pk.sign_recoverable(rawhash, hasher=None)
        v = safe_ord(signature[64]) + 27
        r = big_endian_to_int(signature[0:32])
        s = big_endian_to_int(signature[32:64])
    else:
        v, r, s = ecdsa_raw_sign(rawhash, key)
    return v, r, s

def sha3(x):
    return keccak.new(digest_bits=256, data=x).digest()

def int_to_big_endian(x):
    return big_endian_int.serialize(x)

def zpad(x, l):
    return b"\x00" * max(0, l - len(x)) + x

def encode_int32(v):
    return zpad(int_to_big_endian(v), 32)

def generate_vrs(data: List[List[Any]], private_key: str) -> Dict[str, Any]:
    # pack parameters based on type
    sig_str = b""
    for d in data:
        val = d[1]
        if d[2] == "address":
            # remove 0x prefix and convert to bytes
            val = val[2:].encode("utf-8")
        elif d[2] == "uint256":
            # encode, pad and convert to bytes
            val = binascii.b2a_hex(encode_int32(int(d[1])))
        sig_str += val
    # hash the packed string
    rawhash = sha3(codecs.decode(sig_str, "hex_codec"))
    # salt the hashed packed string
    salted = sha3(u"\x19Ethereum Signed Message:\n32".encode("utf-8") + rawhash)
    # sign string
    v, r, s = ecsign(salted, codecs.decode(private_key[2:], "hex_codec"))
    # # pad r and s with 0 to 64 places
    return {
        "v": v,
        "r": "{0:#0{1}x}".format(r, 66),
        "s": "{0:#0{1}x}".format(s, 66)
    }
