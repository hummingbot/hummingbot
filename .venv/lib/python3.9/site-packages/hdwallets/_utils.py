import hashlib
import hmac
import re
from typing import Iterable, List, Optional, Tuple

import ecdsa

CURVE_GEN = ecdsa.ecdsa.generator_secp256k1
CURVE_ORDER = CURVE_GEN.order()
REGEX_DERIVATION_PATH = re.compile("^m(/[0-9]+['hH]?)*$")
HARDENED_INDEX = 0x80000000
ENCODING_PREFIX = {
    "main": {"private": 0x0488ADE4, "public": 0x0488B21E},
    "test": {"private": 0x04358394, "public": 0x043587CF},
}


class BIP32DerivationError(Exception):
    """We derived an invalid (secret > N or point(secret) is infinity) key!"""


def _privkey_to_pubkey(privkey: bytes) -> bytes:
    """Takes a 32 bytes privkey and returns a 33 bytes secp256k1 pubkey."""
    privkey_obj = ecdsa.SigningKey.from_string(privkey, curve=ecdsa.SECP256k1)
    pubkey_obj = privkey_obj.get_verifying_key()
    return pubkey_obj.to_string("compressed")


def _derive_private_child(
    privkey: bytes, chaincode: bytes, index: int
) -> Tuple[bytes, bytes]:
    """A.k.a CKDpriv, in bip-0032.

    :param privkey: The parent's private key, as bytes
    :param chaincode: The parent's chaincode, as bytes
    :param index: The index of the node to derive, as int

    :return: (child_privatekey, child_chaincode)
    """
    hardened = bool(index & HARDENED_INDEX)
    if hardened:
        payload_key = b"\x00" + privkey
    else:
        payload_key = _privkey_to_pubkey(privkey)
    # payload is the I from the BIP. Index is 32 bits unsigned int, BE.
    payload = hmac.new(
        chaincode, payload_key + index.to_bytes(4, "big"), hashlib.sha512
    ).digest()

    payload_left = payload[:32]
    payload_left_int = int.from_bytes(payload_left, "big")
    if payload_left_int >= CURVE_ORDER:
        raise BIP32DerivationError(
            f"Invalid private key at index {index}, try the next one!"
        )
    privkey_int = int.from_bytes(privkey, "big")
    k_int = (payload_left_int + privkey_int) % CURVE_ORDER
    if k_int == 0:
        raise BIP32DerivationError(
            f"Invalid private key at index {index}, try the next one!"
        )
    secret = k_int.to_bytes(32, "big")

    return secret, payload[32:]


def _derive_public_child(
    pubkey: bytes, chaincode: bytes, index: int
) -> Tuple[bytes, bytes]:
    """A.k.a CKDpub, in bip-0032.

    :param pubkey: The parent's (compressed) public key, as bytes
    :param chaincode: The parent's chaincode, as bytes
    :param index: The index of the node to derive, as int

    :return: (child_pubkey, child_chaincode)
    """
    assert not index & HARDENED_INDEX
    # payload is the I from the BIP. Index is 32 bits unsigned int, BE.
    payload = hmac.new(
        chaincode, pubkey + index.to_bytes(4, "big"), hashlib.sha512
    ).digest()

    payload_left = payload[:32]
    payload_left_int = int.from_bytes(payload_left, "big")
    if payload_left_int >= CURVE_ORDER:
        raise BIP32DerivationError(
            f"Invalid private key at index {index}, try the next one!"
        )
    pubkey_point = ecdsa.VerifyingKey.from_string(
        pubkey, curve=ecdsa.SECP256k1
    ).pubkey.point
    point = payload_left_int * CURVE_GEN + pubkey_point
    if point == ecdsa.ellipticcurve.INFINITY:
        raise BIP32DerivationError(
            f"Invalid public key at index {index}, try the next one!"
        )

    # Retrieve public key based on curve point
    child_pub = ecdsa.VerifyingKey.from_public_point(
        point, curve=ecdsa.SECP256k1
    ).to_string("compressed")

    return child_pub, payload[32:]


def _pubkey_to_fingerprint(pubkey: bytes) -> bytes:
    sha_digest = hashlib.new("sha256", pubkey).digest()
    ripe_digest = hashlib.new("ripemd160", sha_digest).digest()
    return ripe_digest[:4]


def _serialize_extended_key(
    key: bytes,
    depth: int,
    parent: Optional[bytes],
    index: int,
    chaincode: bytes,
    network: str = "main",
) -> bytes:
    """Serialize an extended private *OR* public key, as spec by bip-0032.

    :param key: The public or private key to serialize. Note that if this is
                a public key it MUST be compressed.
    :param depth: 0x00 for master nodes, 0x01 for level-1 derived keys, etc..
    :param parent: The parent pubkey used to derive the fingerprint, or the
                   fingerprint itself None if master.
    :param index: The index of the key being serialized. 0x00000000 if master.
    :param chaincode: The chain code (not the labs !!).

    :return: The serialized extended key.
    """
    if parent:
        if len(parent) == 33:
            fingerprint = _pubkey_to_fingerprint(parent)
        elif len(parent) == 4:
            fingerprint = parent
        else:
            raise ValueError("Bad parent, a fingerprint or a pubkey is required")
    else:
        fingerprint = bytes(4)  # master
    # A privkey or a compressed pubkey
    assert len(key) in {32, 33}
    if network not in {"main", "test"}:
        raise ValueError("Unsupported network")
    is_privkey = len(key) == 32
    prefix = ENCODING_PREFIX[network]["private" if is_privkey else "public"]
    extended = prefix.to_bytes(4, "big")
    extended += depth.to_bytes(1, "big")
    extended += fingerprint
    extended += index.to_bytes(4, "big")
    extended += chaincode
    if is_privkey:
        extended += b"\x00"
    extended += key
    return extended


def _unserialize_extended_key(
    extended_key: bytes,
) -> Tuple[str, int, bytes, int, bytes, bytes]:
    """Unserialize an extended private *OR* public key, as spec by bip-0032.

    :param extended_key: The extended key to unserialize __as bytes__

    :return: network (str), depth (int), fingerprint (bytes), index (int),
             chaincode (bytes), key (bytes)
    """
    assert len(extended_key) == 78
    prefix = int.from_bytes(extended_key[:4], "big")
    if prefix in ENCODING_PREFIX["main"].values():
        network = "main"
    else:
        network = "test"
    depth = extended_key[4]
    fingerprint = extended_key[5:9]
    index = int.from_bytes(extended_key[9:13], "big")
    chaincode, key = extended_key[13:45], extended_key[45:]
    return network, depth, fingerprint, index, chaincode, key


def _hardened_index_in_path(path: Iterable[int]) -> bool:
    return any(i & HARDENED_INDEX for i in path)


def _deriv_path_str_to_list(strpath: str) -> List[int]:
    """Converts a derivation path as string to a list of integers (index of
    each depth)

    :param strpath: Derivation path as string with "m/x/x'/x" notation.
                    (e.g. m/0'/1/2'/2 or m/0H/1/2H/2 or m/0h/1/2h/2)

    :return: Derivation path as a list of integers (index of each depth)
    """
    if not REGEX_DERIVATION_PATH.match(strpath):
        raise ValueError("invalid format")
    indexes = strpath.split("/")[1:]
    list_path = []
    for i in indexes:
        # if HARDENED
        if i[-1:] in ["'", "h", "H"]:
            list_path.append(int(i[:-1]) + HARDENED_INDEX)
        else:
            list_path.append(int(i))
    return list_path
