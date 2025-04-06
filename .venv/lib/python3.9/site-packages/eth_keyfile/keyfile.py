import hashlib
import hmac
import io
import json
from typing import (
    IO,
    Any,
    AnyStr,
    Callable,
    Dict,
    Iterable,
    Literal,
    Mapping,
    Tuple,
    TypeVar,
    Union,
    cast,
)
import uuid

from Crypto import (
    Random,
)
from Crypto.Cipher import (
    AES,
)
from Crypto.Protocol.KDF import (
    scrypt,
)
from Crypto.Util import (
    Counter,
)
from eth_keys import (
    keys,
)
from eth_typing import (
    HexStr,
)
from eth_utils import (
    big_endian_to_int,
    decode_hex,
    encode_hex,
    int_to_big_endian,
    is_dict,
    is_string,
    keccak,
    remove_0x_prefix,
    to_dict,
)

KDFType = Literal["pbkdf2", "scrypt"]
TKey = TypeVar("TKey")
TVal = TypeVar("TVal")
typed_to_dict = cast(
    Callable[
        [Callable[..., Iterable[Union[Mapping[TKey, TVal], Tuple[TKey, TVal]]]]],
        Callable[..., Dict[TKey, TVal]],
    ],
    to_dict,
)


def encode_hex_no_prefix(value: AnyStr) -> HexStr:
    return remove_0x_prefix(encode_hex(value))


def load_keyfile(path_or_file_obj: Union[str, IO[str]]) -> Any:
    if is_string(path_or_file_obj):
        assert isinstance(path_or_file_obj, str)
        with open(path_or_file_obj) as keyfile_file:
            return json.load(keyfile_file)
    else:
        assert isinstance(path_or_file_obj, io.TextIOBase)
        return json.load(path_or_file_obj)


def create_keyfile_json(
    private_key: Union[bytes, bytearray, memoryview],
    password: str,
    version: int = 3,
    kdf: KDFType = "pbkdf2",
    iterations: Union[int, None] = None,
    salt_size: int = 16,
) -> Dict[str, Any]:
    if version == 3:
        return _create_v3_keyfile_json(
            private_key, password, kdf, iterations, salt_size
        )
    else:
        raise NotImplementedError("Not yet implemented")


def decode_keyfile_json(raw_keyfile_json: Dict[Any, Any], password: str) -> bytes:
    keyfile_json = normalize_keys(raw_keyfile_json)
    version = keyfile_json["version"]

    if version == 3:
        return _decode_keyfile_json_v3(keyfile_json, password)
    if version == 4:
        return _decode_keyfile_json_v4(keyfile_json, password)
    else:
        raise NotImplementedError("Not yet implemented")


def extract_key_from_keyfile(
    path_or_file_obj: Union[str, IO[str]], password: str
) -> bytes:
    keyfile_json = load_keyfile(path_or_file_obj)
    private_key = decode_keyfile_json(keyfile_json, password)
    return private_key


@typed_to_dict
def normalize_keys(keyfile_json: Dict[Any, Any]) -> Any:
    for key, value in keyfile_json.items():
        if is_string(key):
            norm_key = key.lower()
        else:
            norm_key = key

        if is_dict(value):
            norm_value = normalize_keys(value)
        else:
            norm_value = value

        yield norm_key, norm_value


#
# Version 3 creators
#
DKLEN = 32
SCRYPT_R = 8
SCRYPT_P = 1


def _create_v3_keyfile_json(
    private_key: Union[bytes, bytearray, memoryview],
    password: str,
    kdf: KDFType,
    work_factor: Union[int, None] = None,
    salt_size: int = 16,
) -> Dict[str, Any]:
    salt = Random.get_random_bytes(salt_size)

    if work_factor is None:
        work_factor = get_default_work_factor_for_kdf(kdf)

    if kdf == "pbkdf2":
        derived_key = _pbkdf2_hash(
            password,
            hash_name="sha256",
            salt=salt,
            iterations=work_factor,
            dklen=DKLEN,
        )
        kdfparams = {
            "c": work_factor,
            "dklen": DKLEN,
            "prf": "hmac-sha256",
            "salt": encode_hex_no_prefix(salt),
        }
    elif kdf == "scrypt":
        derived_key = _scrypt_hash(
            password,
            salt=salt,
            buflen=DKLEN,
            r=SCRYPT_R,
            p=SCRYPT_P,
            n=work_factor,
        )
        kdfparams = {
            "dklen": DKLEN,
            "n": work_factor,
            "r": SCRYPT_R,
            "p": SCRYPT_P,
            "salt": encode_hex_no_prefix(salt),
        }
    else:
        raise NotImplementedError(f"KDF not implemented: {kdf}")

    iv = big_endian_to_int(Random.get_random_bytes(16))
    encrypt_key = derived_key[:16]
    ciphertext = encrypt_aes_ctr(private_key, encrypt_key, iv)
    mac = keccak(derived_key[16:32] + ciphertext)

    address = keys.PrivateKey(private_key).public_key.to_checksum_address()

    return {
        "address": remove_0x_prefix(address),
        "crypto": {
            "cipher": "aes-128-ctr",
            "cipherparams": {
                "iv": encode_hex_no_prefix(int_to_big_endian(iv)),
            },
            "ciphertext": encode_hex_no_prefix(ciphertext),
            "kdf": kdf,
            "kdfparams": kdfparams,
            "mac": encode_hex_no_prefix(mac),
        },
        "id": str(uuid.uuid4()),
        "version": 3,
    }


#
# Verson 3 decoder
#
def _decode_keyfile_json_v3(keyfile_json: Dict[str, Any], password: str) -> bytes:
    crypto = keyfile_json["crypto"]
    kdf = crypto["kdf"]

    # Derive the encryption key from the password using the key derivation
    # function.
    if kdf == "pbkdf2":
        derived_key = _derive_pbkdf_key(crypto["kdfparams"], password)
    elif kdf == "scrypt":
        derived_key = _derive_scrypt_key(crypto["kdfparams"], password)
    else:
        raise TypeError(f"Unsupported key derivation function: {kdf}")

    # Validate that the derived key matchs the provided MAC
    ciphertext = decode_hex(crypto["ciphertext"])
    mac = keccak(derived_key[16:32] + ciphertext)

    expected_mac = decode_hex(crypto["mac"])

    if not hmac.compare_digest(mac, expected_mac):
        raise ValueError("MAC mismatch")

    # Decrypt the ciphertext using the derived encryption key to get the
    # private key.
    encrypt_key = derived_key[:16]
    cipherparams = crypto["cipherparams"]
    iv = big_endian_to_int(decode_hex(cipherparams["iv"]))

    private_key = decrypt_aes_ctr(ciphertext, encrypt_key, iv)

    return private_key


#
# Verson 4 decoder
#
def _decode_keyfile_json_v4(keyfile_json: Dict[str, Any], password: str) -> bytes:
    crypto = keyfile_json["crypto"]
    kdf = crypto["kdf"]["function"]

    # Derive the encryption key from the password using the key derivation
    # function.
    if kdf == "pbkdf2":
        derived_key = _derive_pbkdf_key(crypto["kdf"]["params"], password)
    elif kdf == "scrypt":
        derived_key = _derive_scrypt_key(crypto["kdf"]["params"], password)
    else:
        raise TypeError(f"Unsupported key derivation function: {kdf}")

    cipher_message = decode_hex(crypto["cipher"]["message"])
    checksum_message = crypto["checksum"]["message"]

    if (
        hashlib.sha256(derived_key[16:32] + cipher_message).hexdigest()
        != checksum_message
    ):
        raise ValueError("Checksum mismatch")

    # Decrypt the cipher message using the derived encryption key to get the
    # private key.
    encrypt_key = derived_key[:16]
    cipherparams = crypto["cipher"]["params"]
    iv = big_endian_to_int(decode_hex(cipherparams["iv"]))

    private_key = decrypt_aes_ctr(cipher_message, encrypt_key, iv)

    return private_key


#
# Key derivation
#
def _derive_pbkdf_key(kdf_params: Dict[str, Any], password: str) -> bytes:
    salt = decode_hex(kdf_params["salt"])
    dklen = kdf_params["dklen"]
    should_be_hmac, _, hash_name = kdf_params["prf"].partition("-")
    assert should_be_hmac == "hmac"
    iterations = kdf_params["c"]

    derive_pbkdf_key = _pbkdf2_hash(password, hash_name, salt, iterations, dklen)

    return derive_pbkdf_key


def _derive_scrypt_key(kdf_params: Dict[str, Any], password: str) -> bytes:
    salt = decode_hex(kdf_params["salt"])
    p = kdf_params["p"]
    r = kdf_params["r"]
    n = kdf_params["n"]
    buflen = kdf_params["dklen"]

    derived_scrypt_key = _scrypt_hash(
        password,
        salt=salt,
        n=n,
        r=r,
        p=p,
        buflen=buflen,
    )
    return derived_scrypt_key


def _scrypt_hash(
    password: str, salt: bytes, n: int, r: int, p: int, buflen: int
) -> bytes:
    derived_key = scrypt(
        password,
        salt=salt,
        key_len=buflen,
        N=n,
        r=r,
        p=p,
        num_keys=1,
    )
    return cast(bytes, derived_key)


def _pbkdf2_hash(
    password: Any, hash_name: str, salt: bytes, iterations: int, dklen: int
) -> bytes:
    derived_key = hashlib.pbkdf2_hmac(
        hash_name=hash_name,
        password=password,
        salt=salt,
        iterations=iterations,
        dklen=dklen,
    )

    return derived_key


#
# Encryption and Decryption
#
def decrypt_aes_ctr(ciphertext: bytes, key: bytes, iv: int) -> bytes:
    ctr = Counter.new(128, initial_value=iv, allow_wraparound=True)
    encryptor = AES.new(key, AES.MODE_CTR, counter=ctr)
    return cast(bytes, encryptor.decrypt(ciphertext))


def encrypt_aes_ctr(
    value: Union[bytes, bytearray, memoryview], key: bytes, iv: int
) -> bytes:
    ctr = Counter.new(128, initial_value=iv, allow_wraparound=True)
    encryptor = AES.new(key, AES.MODE_CTR, counter=ctr)
    ciphertext = encryptor.encrypt(value)
    return cast(bytes, ciphertext)


#
# Utility
#
def get_default_work_factor_for_kdf(kdf: KDFType) -> int:
    if kdf == "pbkdf2":
        return 1000000
    elif kdf == "scrypt":
        return 262144
    else:
        raise ValueError(f"Unsupported key derivation function: {kdf}")
