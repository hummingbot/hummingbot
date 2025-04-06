import coincurve
import hashlib
import hmac
import re


REGEX_DERIVATION_PATH = re.compile("^m(/[0-9]+['hH]?)*$")
HARDENED_INDEX = 0x80000000
ENCODING_PREFIX = {
    "main": {
        "private": 0x0488ADE4,
        "public": 0x0488B21E,
    },
    "test": {
        "private": 0x04358394,
        "public": 0x043587CF,
    },
}


class BIP32DerivationError(Exception):
    """We derived an invalid (secret > N or point(secret) is infinity) key!"""


def _privkey_is_valid(privkey):
    """Takes bytes and returns True if it's a valid secp256k1 privkey"""
    try:
        coincurve.PrivateKey(privkey)
        return True
    except ValueError:
        return False


def _pubkey_is_valid(pubkey):
    """Takes bytes and returns True if it's a valid secp256k1 pubkey"""
    try:
        coincurve.PublicKey(pubkey)
        return True
    except ValueError:
        return False


def _privkey_to_pubkey(privkey):
    """Takes a 32 bytes privkey and returns a 33 bytes secp256k1 pubkey"""
    return coincurve.PublicKey.from_secret(privkey).format()


def _derive_unhardened_private_child(privkey, chaincode, index):
    """A.k.a CKDpriv, in bip-0032

    :param privkey: The parent's private key, as bytes
    :param chaincode: The parent's chaincode, as bytes
    :param index: The index of the node to derive, as int

    :return: (child_privatekey, child_chaincode)
    """
    assert isinstance(privkey, bytes) and isinstance(chaincode, bytes)
    assert not index & HARDENED_INDEX
    pubkey = _privkey_to_pubkey(privkey)
    # payload is the I from the BIP. Index is 32 bits unsigned int, BE.
    payload = hmac.new(
        chaincode, pubkey + index.to_bytes(4, "big"), hashlib.sha512
    ).digest()
    try:
        child_private = coincurve.PrivateKey(payload[:32]).add(privkey)
    except ValueError:
        raise BIP32DerivationError(
            "Invalid private key at index {}, try the " "next one!".format(index)
        )
    return child_private.secret, payload[32:]


def _derive_hardened_private_child(privkey, chaincode, index):
    """A.k.a CKDpriv, in bip-0032, but the hardened way

    :param privkey: The parent's private key, as bytes
    :param chaincode: The parent's chaincode, as bytes
    :param index: The index of the node to derive, as int

    :return: (child_privatekey, child_chaincode)
    """
    assert isinstance(privkey, bytes) and isinstance(chaincode, bytes)
    assert index & HARDENED_INDEX
    # payload is the I from the BIP. Index is 32 bits unsigned int, BE.
    payload = hmac.new(
        chaincode, b"\x00" + privkey + index.to_bytes(4, "big"), hashlib.sha512
    ).digest()
    try:
        child_private = coincurve.PrivateKey(payload[:32]).add(privkey)
    except ValueError:
        raise BIP32DerivationError(
            "Invalid private key at index {}, try the " "next one!".format(index)
        )
    return child_private.secret, payload[32:]


def _derive_public_child(pubkey, chaincode, index):
    """A.k.a CKDpub, in bip-0032.

    :param pubkey: The parent's (compressed) public key, as bytes
    :param chaincode: The parent's chaincode, as bytes
    :param index: The index of the node to derive, as int

    :return: (child_pubkey, child_chaincode)
    """
    assert isinstance(pubkey, bytes) and isinstance(chaincode, bytes)
    assert not index & HARDENED_INDEX
    # payload is the I from the BIP. Index is 32 bits unsigned int, BE.
    payload = hmac.new(
        chaincode, pubkey + index.to_bytes(4, "big"), hashlib.sha512
    ).digest()
    try:
        tmp_pub = coincurve.PublicKey.from_secret(payload[:32])
    except ValueError:
        raise BIP32DerivationError(
            "Invalid private key at index {}, try the " "next one!".format(index)
        )
    parent_pub = coincurve.PublicKey(pubkey)
    try:
        child_pub = coincurve.PublicKey.combine_keys([tmp_pub, parent_pub])
    except ValueError:
        raise BIP32DerivationError(
            "Invalid public key at index {}, try the " "next one!".format(index)
        )
    return child_pub.format(), payload[32:]


def _ripemd160(data):
    try:
        rip = hashlib.new("ripemd160")
        rip.update(data)
        return rip.digest()
    except BaseException:
        # Implementations may ship hashlib without ripemd160.
        # In that case, fallback to custom pure Python implementation.
        # WARNING: the implementation in ripemd160.py is not constant-time.
        from . import ripemd160

        return ripemd160.ripemd160(data)


def _pubkey_to_fingerprint(pubkey):
    return _ripemd160(hashlib.sha256(pubkey).digest())[:4]


def _serialize_extended_key(key, depth, parent, index, chaincode, network="main"):
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
    for param in {key, chaincode}:
        assert isinstance(param, bytes)
    for param in {depth, index}:
        assert isinstance(param, int)
    if parent:
        assert isinstance(parent, bytes)
        if len(parent) == 33:
            fingerprint = _pubkey_to_fingerprint(parent)
        elif len(parent) == 4:
            fingerprint = parent
        else:
            raise ValueError("Bad parent, a fingerprint or a pubkey is" " required")
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


def _unserialize_extended_key(extended_key):
    """Unserialize an extended private *OR* public key, as spec by bip-0032.

    :param extended_key: The extended key to unserialize __as bytes__

    :return: network (str), depth (int), fingerprint (bytes), index (int),
             chaincode (bytes), key (bytes)
    """
    assert isinstance(extended_key, bytes) and len(extended_key) == 78
    prefix = int.from_bytes(extended_key[:4], "big")
    network = None
    if prefix in list(ENCODING_PREFIX["main"].values()):
        network = "main"
    elif prefix in list(ENCODING_PREFIX["test"].values()):
        network = "test"
    depth = extended_key[4]
    fingerprint = extended_key[5:9]
    index = int.from_bytes(extended_key[9:13], "big")
    chaincode, key = extended_key[13:45], extended_key[45:]
    return network, depth, fingerprint, index, chaincode, key


def _hardened_index_in_path(path):
    return len([i for i in path if i & HARDENED_INDEX]) > 0


def _deriv_path_str_to_list(strpath):
    """Converts a derivation path as string to a list of integers
       (index of each depth)

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
