import hashlib
import hmac

from .base58 import b58encode_check, b58decode_check
from .utils import (
    HARDENED_INDEX,
    _derive_hardened_private_child,
    _derive_unhardened_private_child,
    _derive_public_child,
    _serialize_extended_key,
    _unserialize_extended_key,
    _hardened_index_in_path,
    _privkey_to_pubkey,
    _deriv_path_str_to_list,
    _pubkey_is_valid,
    _privkey_is_valid,
    _pubkey_to_fingerprint,
)


class PrivateDerivationError(ValueError):
    """
    Tried to use a derivation requiring private keys, without private keys.
    """

    pass


class InvalidInputError(ValueError):
    def __init__(self, message):
        self.message = message


class ParsingError(ValueError):
    def __init__(self, message):
        self.message = message


class BIP32:
    def __init__(
        self,
        chaincode,
        privkey=None,
        pubkey=None,
        fingerprint=bytes(4),
        depth=0,
        index=0,
        network="main",
    ):
        """
        :param chaincode: The master chaincode, used to derive keys. As bytes.
        :param privkey: The master private key for this index (default 0).
                        Can be None for pubkey-only derivation.
                        As bytes.
        :param pubkey: The master public key for this index (default 0).
                       Can be None if private key is specified.
                       Compressed format. As bytes.
        :param fingeprint: If we are instanciated from an xpub/xpriv, we need
                           to remember the parent's pubkey fingerprint to
                           reserialize !
        :param depth: If we are instanciated from an existing extended key, we
                      need this for serialization.
        :param index: If we are instanciated from an existing extended key, we
                      need this for serialization.
        :param network: Either "main" or "test".
        """
        if network not in ["main", "test"]:
            raise InvalidInputError("'network' must be one of 'main' or 'test'")
        if not isinstance(chaincode, bytes):
            raise InvalidInputError("'chaincode' must be bytes")
        if privkey is None and pubkey is None:
            raise InvalidInputError("Need at least a 'pubkey' or a 'privkey'")
        if privkey is not None:
            if not isinstance(privkey, bytes):
                raise InvalidInputError("'privkey' must be bytes")
            if not _privkey_is_valid(privkey):
                raise InvalidInputError("Invalid secp256k1 private key")
        if pubkey is not None:
            if not isinstance(pubkey, bytes):
                raise InvalidInputError("'pubkey' must be bytes")
            if not _pubkey_is_valid(pubkey):
                raise InvalidInputError("Invalid secp256k1 public key")
        else:
            pubkey = _privkey_to_pubkey(privkey)
        if depth == 0:
            if fingerprint != bytes(4):
                raise InvalidInputError(
                    "Fingerprint must be 0 if depth is 0 (master xpub)"
                )
            if index != 0:
                raise InvalidInputError("Index must be 0 if depth is 0 (master xpub)")
        if network not in ["main", "test"]:
            raise InvalidInputError("Unknown network")

        self.chaincode = chaincode
        self.privkey = privkey
        self.pubkey = pubkey
        self.parent_fingerprint = fingerprint
        self.depth = depth
        self.index = index
        self.network = network

    def get_extended_privkey_from_path(self, path):
        """Get an extended privkey from a derivation path.

        :param path: A list of integers (index of each depth) or a string with
                     m/x/x'/x notation. (e.g. m/0'/1/2'/2 or m/0H/1/2H/2).
        :return: chaincode (bytes), privkey (bytes)
        """
        if self.privkey is None:
            raise PrivateDerivationError

        if isinstance(path, str):
            path = _deriv_path_str_to_list(path)

        chaincode, privkey = self.chaincode, self.privkey
        for index in path:
            if index & HARDENED_INDEX:
                privkey, chaincode = _derive_hardened_private_child(
                    privkey, chaincode, index
                )
            else:
                privkey, chaincode = _derive_unhardened_private_child(
                    privkey, chaincode, index
                )

        return chaincode, privkey

    def get_privkey_from_path(self, path):
        """Get a privkey from a derivation path.

        :param path: A list of integers (index of each depth) or a string with
                     m/x/x'/x notation. (e.g. m/0'/1/2'/2 or m/0H/1/2H/2).
        :return: privkey (bytes)
        """
        if self.privkey is None:
            raise PrivateDerivationError

        return self.get_extended_privkey_from_path(path)[1]

    def get_extended_pubkey_from_path(self, path):
        """Get an extended pubkey from a derivation path.

        :param path: A list of integers (index of each depth) or a string with
                     m/x/x'/x notation. (e.g. m/0'/1/2'/2 or m/0H/1/2H/2).
        :return: chaincode (bytes), pubkey (bytes)
        """
        if isinstance(path, str):
            path = _deriv_path_str_to_list(path)

        if _hardened_index_in_path(path) and self.privkey is None:
            raise PrivateDerivationError

        chaincode, key = self.chaincode, self.privkey
        pubkey = self.pubkey
        # We'll need the private key at some point anyway, so let's derive
        # everything from private keys.
        if _hardened_index_in_path(path):
            for index in path:
                if index & HARDENED_INDEX:
                    key, chaincode = _derive_hardened_private_child(
                        key, chaincode, index
                    )
                else:
                    key, chaincode = _derive_unhardened_private_child(
                        key, chaincode, index
                    )
                pubkey = _privkey_to_pubkey(key)
        # We won't need private keys for the whole path, so let's only use
        # public key derivation.
        else:
            for index in path:
                pubkey, chaincode = _derive_public_child(pubkey, chaincode, index)

        return chaincode, pubkey

    def get_pubkey_from_path(self, path):
        """Get a pubkey from a derivation path.

        :param path: A list of integers (index of each depth) or a string with
                     m/x/x'/x notation. (e.g. m/0'/1/2'/2 or m/0H/1/2H/2).
        :return: privkey (bytes)
        """
        return self.get_extended_pubkey_from_path(path)[1]

    def get_xpriv_from_path(self, path):
        """Get an encoded extended privkey from a derivation path.

        :param path: A list of integers (index of each depth) or a string with
                     m/x/x'/x notation. (e.g. m/0'/1/2'/2 or m/0H/1/2H/2).
        :return: The encoded extended pubkey as str.
        """
        if self.privkey is None:
            raise PrivateDerivationError

        if isinstance(path, str):
            path = _deriv_path_str_to_list(path)

        if len(path) == 0:
            return self.get_xpriv()
        elif len(path) == 1:
            parent_pubkey = self.pubkey
        else:
            parent_pubkey = self.get_pubkey_from_path(path[:-1])
        chaincode, privkey = self.get_extended_privkey_from_path(path)
        extended_key = _serialize_extended_key(
            privkey,
            self.depth + len(path),
            parent_pubkey,
            path[-1],
            chaincode,
            self.network,
        )

        return b58encode_check(extended_key).decode()

    def get_xpub_from_path(self, path):
        """Get an encoded extended pubkey from a derivation path.

        :param path: A list of integers (index of each depth) or a string with
                     m/x/x'/x notation. (e.g. m/0'/1/2'/2 or m/0H/1/2H/2).
        :return: The encoded extended pubkey as str.
        """
        if isinstance(path, str):
            path = _deriv_path_str_to_list(path)

        if _hardened_index_in_path(path) and self.privkey is None:
            raise PrivateDerivationError

        if len(path) == 0:
            return self.get_xpub()
        elif len(path) == 1:
            parent_pubkey = self.pubkey
        else:
            parent_pubkey = self.get_pubkey_from_path(path[:-1])
        chaincode, pubkey = self.get_extended_pubkey_from_path(path)
        extended_key = _serialize_extended_key(
            pubkey,
            self.depth + len(path),
            parent_pubkey,
            path[-1],
            chaincode,
            self.network,
        )

        return b58encode_check(extended_key).decode()

    def get_xpriv(self):
        """Get the base58 encoded extended private key."""
        return b58encode_check(self.get_xpriv_bytes()).decode()

    def get_xpriv_bytes(self):
        """Get the encoded extended private key."""
        if self.privkey is None:
            raise PrivateDerivationError
        return _serialize_extended_key(
            self.privkey,
            self.depth,
            self.parent_fingerprint,
            self.index,
            self.chaincode,
            self.network,
        )

    def get_xpub(self):
        """Get the encoded extended public key."""
        return b58encode_check(self.get_xpub_bytes()).decode()

    def get_xpub_bytes(self):
        """Get the encoded extended public key."""
        return _serialize_extended_key(
            self.pubkey,
            self.depth,
            self.parent_fingerprint,
            self.index,
            self.chaincode,
            self.network,
        )

    def get_fingerprint(self):
        """Get the public key fingerprint."""
        return _pubkey_to_fingerprint(self.pubkey)

    @classmethod
    def from_xpriv(cls, xpriv):
        """Get a BIP32 "wallet" out of this xpriv

        :param xpriv: (str) The encoded serialized extended private key.
        """
        if not isinstance(xpriv, str):
            raise InvalidInputError("'xpriv' must be a string")

        extended_key = b58decode_check(xpriv)
        (
            network,
            depth,
            fingerprint,
            index,
            chaincode,
            key,
        ) = _unserialize_extended_key(extended_key)

        if key[0] != 0:
            raise ParsingError("Invalid xpriv: private key prefix must be 0")

        try:
            # We need to remove the trailing `0` before the actual private key !!
            return BIP32(chaincode, key[1:], None, fingerprint, depth, index, network)
        except InvalidInputError as e:
            raise ParsingError(f"Invalid xpriv: '{e}'")

    @classmethod
    def from_xpub(cls, xpub):
        """Get a BIP32 "wallet" out of this xpub

        :param xpub: (str) The encoded serialized extended public key.
        """
        if not isinstance(xpub, str):
            raise InvalidInputError("'xpub' must be a string")

        extended_key = b58decode_check(xpub)
        (
            network,
            depth,
            fingerprint,
            index,
            chaincode,
            key,
        ) = _unserialize_extended_key(extended_key)

        try:
            return BIP32(chaincode, None, key, fingerprint, depth, index, network)
        except InvalidInputError as e:
            raise ParsingError(f"Invalid xpub: '{e}'")

    @classmethod
    def from_seed(cls, seed, network="main"):
        """Get a BIP32 "wallet" out of this seed (maybe after BIP39?)

        :param seed: The seed as bytes.
        """
        secret = hmac.new("Bitcoin seed".encode(), seed, hashlib.sha512).digest()
        return BIP32(secret[32:], secret[:32], network=network)
