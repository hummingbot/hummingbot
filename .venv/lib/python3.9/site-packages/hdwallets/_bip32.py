import hashlib
import hmac
from typing import Optional, Sequence, Tuple, Union

from ._utils import (
    _deriv_path_str_to_list,
    _derive_private_child,
    _derive_public_child,
    _hardened_index_in_path,
    _privkey_to_pubkey,
    _serialize_extended_key,
    _unserialize_extended_key,
)


class BIP32:
    def __init__(
        self,
        chaincode: bytes,
        privkey: Optional[bytes] = None,
        pubkey: Optional[bytes] = None,
        fingerprint: Optional[bytes] = None,
        depth: int = 0,
        index: int = 0,
        network: str = "main",
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
        if pubkey is None:
            if privkey is None:
                raise ValueError("Must provide privkey or pubkey")
            pubkey = _privkey_to_pubkey(privkey)
        self.master_chaincode = chaincode
        self.master_privkey = privkey
        self.master_pubkey = pubkey
        self.parent_fingerprint = fingerprint
        self.depth = depth
        self.index = index
        self.network = network

    def get_extended_privkey_from_path(
        self, path: Union[Sequence[int], str]
    ) -> Tuple[bytes, bytes]:
        """Get an extended privkey from a derivation path.

        :param path: A list of integers (index of each depth) or a string with
                     m/x/x'/x notation. (e.g. m/0'/1/2'/2 or m/0H/1/2H/2).
        :return: chaincode (bytes), privkey (bytes)
        """
        if isinstance(path, str):
            path = _deriv_path_str_to_list(path)
        chaincode, privkey = self.master_chaincode, self.master_privkey
        assert isinstance(privkey, bytes)
        for index in path:
            privkey, chaincode = _derive_private_child(privkey, chaincode, index)
        return chaincode, privkey

    def get_privkey_from_path(self, path: Union[Sequence[int], str]) -> bytes:
        """Get a privkey from a derivation path.

        :param path: A list of integers (index of each depth) or a string with
                     m/x/x'/x notation. (e.g. m/0'/1/2'/2 or m/0H/1/2H/2).
        :return: privkey (bytes)
        """
        return self.get_extended_privkey_from_path(path)[1]

    def get_extended_pubkey_from_path(
        self, path: Union[Sequence[int], str]
    ) -> Tuple[bytes, bytes]:
        """Get an extended pubkey from a derivation path.

        :param path: A list of integers (index of each depth) or a string with
                     m/x/x'/x notation. (e.g. m/0'/1/2'/2 or m/0H/1/2H/2).
        :return: chaincode (bytes), pubkey (bytes)
        """
        if isinstance(path, str):
            path = _deriv_path_str_to_list(path)
        chaincode, key = self.master_chaincode, self.master_privkey
        # We'll need the private key at some point anyway, so let's derive
        # everything from private keys.
        if _hardened_index_in_path(path):
            for index in path:
                assert isinstance(key, bytes)
                key, chaincode = _derive_private_child(key, chaincode, index)
                pubkey = _privkey_to_pubkey(key)
        # We won't need private keys for the whole path, so let's only use
        # public key derivation.
        else:
            key = self.master_pubkey
            assert isinstance(key, bytes)
            for index in path:
                key, chaincode = _derive_public_child(key, chaincode, index)
                pubkey = key
        return chaincode, pubkey

    def get_pubkey_from_path(self, path: Union[Sequence[int], str]) -> bytes:
        """Get a privkey from a derivation path.

        :param path: A list of integers (index of each depth) or a string with
                     m/x/x'/x notation. (e.g. m/0'/1/2'/2 or m/0H/1/2H/2).
        :return: privkey (bytes)
        """
        return self.get_extended_pubkey_from_path(path)[1]

    def get_xpriv_from_path(self, path: Union[Sequence[int], str]) -> bytes:
        """Get an encoded extended privkey from a derivation path.

        :param path: A list of integers (index of each depth) or a string with
                     m/x/x'/x notation. (e.g. m/0'/1/2'/2 or m/0H/1/2H/2).
        :return: The encoded extended pubkey as bytes.
        """
        if isinstance(path, str):
            path = _deriv_path_str_to_list(path)
        if len(path) == 0:
            return self.get_master_xpriv()
        elif len(path) == 1:
            parent_pubkey = self.master_pubkey
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
        return extended_key

    def get_xpub_from_path(self, path: Union[Sequence[int], str]) -> bytes:
        """Get an encoded extended pubkey from a derivation path.

        :param path: A list of integers (index of each depth) or a string with
                     m/x/x'/x notation. (e.g. m/0'/1/2'/2 or m/0H/1/2H/2).
        :return: The encoded extended pubkey as bytes.
        """
        if isinstance(path, str):
            path = _deriv_path_str_to_list(path)
        if len(path) == 0:
            return self.get_master_xpub()
        elif len(path) == 1:
            parent_pubkey = self.master_pubkey
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
        return extended_key

    def get_master_xpriv(self) -> bytes:
        """Get the encoded extended private key of the master private key."""
        assert isinstance(self.master_privkey, bytes)
        extended_key = _serialize_extended_key(
            self.master_privkey,
            self.depth,
            self.parent_fingerprint,
            self.index,
            self.master_chaincode,
            self.network,
        )
        return extended_key

    def get_master_xpub(self) -> bytes:
        """Get the encoded extended public key of the master public key."""
        extended_key = _serialize_extended_key(
            self.master_pubkey,
            self.depth,
            self.parent_fingerprint,
            self.index,
            self.master_chaincode,
            self.network,
        )
        return extended_key

    @staticmethod
    def from_xpriv(xpriv: bytes) -> "BIP32":
        """Get a BIP32 "wallet" out of this xpriv.

        :param xpriv: (str) The encoded serialized extended private key.
        """
        (
            network,
            depth,
            fingerprint,
            index,
            chaincode,
            key,
        ) = _unserialize_extended_key(xpriv)
        # We need to remove the trailing `0` before the actual private key !!
        return BIP32(chaincode, key[1:], None, fingerprint, depth, index, network)

    @staticmethod
    def from_xpub(xpub: bytes) -> "BIP32":
        """Get a BIP32 "wallet" out of this xpub.

        :param xpub: (str) The encoded serialized extended public key.
        """
        (
            network,
            depth,
            fingerprint,
            index,
            chaincode,
            key,
        ) = _unserialize_extended_key(xpub)
        return BIP32(chaincode, None, key, fingerprint, depth, index, network)

    @staticmethod
    def from_seed(seed: bytes, network: str = "main") -> "BIP32":
        """Get a BIP32 "wallet" out of this seed (maybe after BIP39?)

        :param seed: The seed as bytes.
        """
        secret = hmac.new(b"Bitcoin seed", seed, hashlib.sha512).digest()
        return BIP32(secret[32:], secret[:32], network=network)
