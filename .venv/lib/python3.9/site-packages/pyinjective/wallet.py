import hashlib
import json
from typing import Tuple

import aiohttp
import requests
import sha3
from bech32 import bech32_decode, bech32_encode, convertbits
from bip32 import BIP32
from ecdsa import BadSignatureError, SECP256k1, SigningKey, VerifyingKey
from ecdsa.util import sigencode_string_canonize
from mnemonic import Mnemonic

from pyinjective.exceptions import ConvertError, DecodeError
from pyinjective.proto.injective.crypto.v1beta1.ethsecp256k1.keys_pb2 import PubKey as PubKeyProto

BECH32_PUBKEY_ACC_PREFIX = "injpub"
BECH32_PUBKEY_VAL_PREFIX = "injvaloperpub"
BECH32_PUBKEY_CONS_PREFIX = "injvalconspub"

BECH32_ADDR_ACC_PREFIX = "inj"
BECH32_ADDR_VAL_PREFIX = "injvaloper"
BECH32_ADDR_CONS_PREFIX = "injvalcons"

DEFAULT_DERIVATION_PATH = "m/44'/60'/0'/0/0"


class PrivateKey:
    """
    Class for wrapping SigningKey that is used for signature creation and public key derivation.

    :ivar signing_key: the ecdsa SigningKey instance
    :vartype signing_key: ecdsa.SigningKey
    """

    def __init__(self, _error_do_not_use_init_directly=None) -> None:
        """Unsupported, please use from_mnemonic to initialize."""
        if not _error_do_not_use_init_directly:
            raise TypeError("Please use PrivateKey.from_mnemonic() to construct me")
        self.signing_key: SigningKey = None

    @classmethod
    def generate(cls, path=DEFAULT_DERIVATION_PATH) -> Tuple[str, "PrivateKey"]:
        """
        Generate new private key with random mnemonic phrase

        :param path: the HD path that follows the BIP32 standard

        :return: A tuple of mnemonic phrase and PrivateKey instance
        """
        phrase = Mnemonic(language="english").generate(strength=256)
        return (phrase, cls.from_mnemonic(phrase, path))

    @classmethod
    def from_mnemonic(cls, words: str, path=DEFAULT_DERIVATION_PATH) -> "PrivateKey":
        """
        Create a PrivateKey instance from a given mnemonic phrase and a HD derivation path.
        If path is not given, default to Band's HD prefix 494 and all other indexes being zeroes.

        :param words: the mnemonic phrase for recover private key
        :param path: the HD path that follows the BIP32 standard

        :return: Initialized PrivateKey object
        """
        seed = Mnemonic("english").to_seed(words)
        self = cls(_error_do_not_use_init_directly=True)
        self.signing_key = SigningKey.from_string(
            BIP32.from_seed(seed).get_privkey_from_path(path), curve=SECP256k1, hashfunc=hashlib.sha256
        )
        return self

    @classmethod
    def from_hex(cls, priv: str) -> "PrivateKey":
        self = cls(_error_do_not_use_init_directly=True)
        self.signing_key = SigningKey.from_string(bytes.fromhex(priv), curve=SECP256k1, hashfunc=hashlib.sha256)
        return self

    def to_hex(self) -> str:
        """
        Return a hex representation of signing key.
        """
        return self.signing_key.to_string().hex()

    def to_public_key(self) -> "PublicKey":
        """
        Return the PublicKey associated with this private key.

        :return: a PublicKey that can be used to verify the signatures made with this PrivateKey
        """
        public_key = PublicKey(_error_do_not_use_init_directly=True)
        public_key.verify_key = self.signing_key.get_verifying_key()
        return public_key

    def sign(self, msg: bytes) -> bytes:
        """
        Sign the given message using the edcsa sign_deterministic function.

        :param msg: the message that will be hashed and signed

        :return: a signature of this private key over the given message
        """

        return self.signing_key.sign_deterministic(msg, hashfunc=sha3.keccak_256, sigencode=sigencode_string_canonize)


class PublicKey:
    """
    Class for wrapping VerifyKey using for signature verification. Adding method to encode/decode
    to Bech32 format.

    :ivar verify_key: the ecdsa VerifyingKey instance
    :vartype verify_key: ecdsa.VerifyingKey
    """

    def __init__(self, _error_do_not_use_init_directly=None) -> None:
        """Unsupported, please do not construct it directly."""
        if not _error_do_not_use_init_directly:
            raise TypeError("Please use PublicKey's factory methods to construct me")
        self.verify_key: VerifyingKey = None

    @classmethod
    def _from_bech32(cls, bech: str, prefix: str) -> "PublicKey":
        hrp, bz = bech32_decode(bech)
        assert hrp == prefix, "Invalid bech32 prefix"
        if bz is None:
            raise DecodeError("Cannot decode bech32")
        bz = convertbits(bz, 5, 8, False)
        self = cls(_error_do_not_use_init_directly=True)
        self.verify_key = VerifyingKey.from_string(bytes(bz[5:]), curve=SECP256k1, hashfunc=hashlib.sha256)
        return self

    @classmethod
    def from_acc_bech32(cls, bech: str) -> "PublicKey":
        return cls._from_bech32(bech, BECH32_PUBKEY_ACC_PREFIX)

    @classmethod
    def from_val_bech32(cls, bech: str) -> "PublicKey":
        return cls._from_bech32(bech, BECH32_PUBKEY_VAL_PREFIX)

    @classmethod
    def from_cons_bech32(cls, bech: str) -> "PublicKey":
        return cls._from_bech32(bech, BECH32_PUBKEY_CONS_PREFIX)

    def to_hex(self) -> str:
        """
        Return a hex representation of verified key.
        """
        return self.verify_key.to_string("compressed").hex()

    def to_public_key_proto(self) -> PubKeyProto:
        return PubKeyProto(key=self.verify_key.to_string("compressed"))

    def _to_bech32(self, prefix: str) -> str:
        five_bit_r = convertbits(
            # Append prefix public key type follow amino spec.
            bytes.fromhex("eb5ae98721") + self.verify_key.to_string("compressed"),
            8,
            5,
        )
        assert five_bit_r is not None, "Unsuccessful bech32.convertbits call"
        return bech32_encode(prefix, five_bit_r)

    def to_acc_bech32(self) -> str:
        """Return bech32-encoded with account public key prefix"""
        return self._to_bech32(BECH32_PUBKEY_ACC_PREFIX)

    def to_val_bech32(self) -> str:
        """Return bech32-encoded with validator public key prefix"""
        return self._to_bech32(BECH32_PUBKEY_VAL_PREFIX)

    def to_cons_bech32(self) -> str:
        """Return bech32-encoded with validator consensus public key prefix"""
        return self._to_bech32(BECH32_PUBKEY_CONS_PREFIX)

    def to_address(self) -> "Address":
        """Return address instance from this public key"""
        pubkey = self.verify_key.to_string("uncompressed")
        keccak_hash = sha3.keccak_256()
        keccak_hash.update(pubkey[1:])
        addr = keccak_hash.digest()[12:]
        return Address(addr)

    def verify(self, msg: bytes, sig: bytes) -> bool:
        """
        Verify a signature made from the given message.

        :param msg: data signed by the `signature`, will be hashed using sha256 function
        :param sig: encoding of the signature

        :raises BadSignatureError: if the signature is invalid or malformed
        :return: True if the verification was successful
        """
        try:
            return self.verify_key.verify(sig, msg, hashfunc=hashlib.sha256)
        except BadSignatureError:
            return False


class Address:
    def __init__(self, addr: bytes) -> None:
        self.addr = addr
        self.number = 0
        self.sequence = 0

    def __eq__(self, o: "Address") -> bool:
        return self.addr == o.addr

    @classmethod
    def _from_bech32(cls, bech: str, prefix: str) -> "Address":
        hrp, bz = bech32_decode(bech)
        assert hrp == prefix, "Invalid bech32 prefix"
        if bz is None:
            raise DecodeError("Cannot decode bech32")
        eight_bit_r = convertbits(bz, 5, 8, False)
        if eight_bit_r is None:
            raise ConvertError("Cannot convert to 8 bit")

        return cls(bytes(eight_bit_r))

    @classmethod
    def from_acc_bech32(cls, bech: str) -> "Address":
        """Create an address instance from a bech32-encoded account address"""
        return cls._from_bech32(bech, BECH32_ADDR_ACC_PREFIX)

    @classmethod
    def from_val_bech32(cls, bech: str) -> "Address":
        """Create an address instance from a bech32-encoded validator address"""
        return cls._from_bech32(bech, BECH32_ADDR_VAL_PREFIX)

    @classmethod
    def from_cons_bech32(cls, bech: str) -> "Address":
        """Create an address instance from a bech32-encoded consensus address"""
        return cls._from_bech32(bech, BECH32_ADDR_CONS_PREFIX)

    def _to_bech32(self, prefix: str) -> str:
        five_bit_r = convertbits(self.addr, 8, 5)
        assert five_bit_r is not None, "Unsuccessful bech32.convertbits call"
        return bech32_encode(prefix, five_bit_r)

    def to_acc_bech32(self) -> str:
        """Return a bech32-encoded account address"""
        return self._to_bech32(BECH32_ADDR_ACC_PREFIX)

    def to_val_bech32(self) -> str:
        """Return a bech32-encoded validator address"""
        return self._to_bech32(BECH32_ADDR_VAL_PREFIX)

    def to_cons_bech32(self) -> str:
        """Return a bech32-encoded with consensus address"""
        return self._to_bech32(BECH32_ADDR_CONS_PREFIX)

    def to_hex(self) -> str:
        """Return a hex representation of address"""
        return self.addr.hex()

    def get_subaccount_id(self, index: int) -> str:
        """Return a hex representation of address"""
        id = index.to_bytes(12, byteorder="big").hex()
        return "0x" + self.addr.hex() + id

    def get_ethereum_address(self) -> str:
        return "0x" + self.addr.hex()

    async def async_init_num_seq(self, lcd_endpoint: str) -> "Address":
        async with aiohttp.ClientSession() as session:
            async with session.request(
                "GET",
                lcd_endpoint + "/cosmos/auth/v1beta1/accounts/" + self.to_acc_bech32(),
                headers={"Accept-Encoding": "application/json"},
            ) as response:
                if response.status != 200:
                    print(await response.text())
                    raise ValueError("HTTP response status", response.status)

                resp = json.loads(await response.text())
                acc = resp["account"]["base_account"]
                self.number = int(acc["account_number"])
                self.sequence = int(acc["sequence"])
                return self

    def init_num_seq(self, lcd_endpoint: str) -> "Address":
        response = requests.get(
            url=f"{lcd_endpoint}/cosmos/auth/v1beta1/accounts/{self.to_acc_bech32()}",
            headers={"Accept-Encoding": "application/json"},
        )
        if response.status_code != 200:
            raise ValueError("HTTP response status", response.status_code)
        resp = json.loads(response.text)
        acc = resp["account"]["base_account"]
        self.number = int(acc["account_number"])
        self.sequence = int(acc["sequence"])
        return self

    def get_sequence(self):
        current_seq = self.sequence
        self.sequence += 1
        return current_seq

    def get_number(self):
        return self.number
